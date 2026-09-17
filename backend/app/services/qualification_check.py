"""组织资质 AI 预检：识别证明材料并核对关键信息。

AI 结果只给平台管理员做辅助判断；人工审核仍是最终结论。
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re

from sqlalchemy.orm import Session

from ..config import UPLOAD_DIR
from ..models import OrgQualification
from ..services import llm_service

logger = logging.getLogger("salted_fish.qualification_check")

SETTING_QUALIFICATION_CHECK = "qualification_ai_check_enabled"

MATERIAL_TYPE_LABEL = {
    "teacher_certificate": "教师资格证",
    "general_certificate": "通用资质证明",
    "other": "其他资质证明",
}

AI_SYSTEM_PROMPT = (
    "你是教育类社区平台的资质审核助手。请仔细识别证明材料照片，"
    "判断证件版式、文字、印章、日期与编号是否自然一致，是否存在翻拍、裁剪、拼接、"
    "明显模板伪造或关键信息遮挡。不要仅凭文字内容判断真伪。"
    "请只返回 JSON，格式："
    '{"valid": true或false, "authenticity": "authentic|suspected_fake|unclear", '
    '"confidence": 0到1, "holder_name": "识别到的姓名", '
    '"certificate_no": "识别到的编号", "issue_date": "识别到的发证或有效期日期", '
    '"checks": [{"name":"版式与印章","passed":true,"note":"一句话"}], '
    '"reason": "一句话中文结论"}'
)


def is_ai_check_enabled(db: Session) -> bool:
    from . import org_service

    raw = org_service.get_setting(db, SETTING_QUALIFICATION_CHECK, "1")
    return str(raw).strip() not in ("0", "false", "False", "off")


def _to_data_url(path: str) -> str | None:
    ext = os.path.splitext(path)[1].lstrip(".").lower() or "png"
    mime = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
        "gif": "image/gif",
    }.get(ext, "image/png")
    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f"data:{mime};base64,{b64}"
    except Exception as e:  # noqa: BLE001
        logger.warning("读取资质材料失败 %s: %s", path, e)
        return None


def _build_content_parts(qualification: OrgQualification, user_text: str) -> list | None:
    parts = [
        {"type": "text", "text": AI_SYSTEM_PROMPT},
        {"type": "text", "text": user_text},
    ]
    added = 0
    for url in qualification.material_list()[:3]:
        data_url = None
        if url.startswith("/uploads/"):
            local = os.path.join(UPLOAD_DIR, os.path.basename(url))
            if os.path.exists(local):
                data_url = _to_data_url(local)
        elif url.startswith("data:") or url.startswith("http"):
            data_url = url
        if data_url:
            parts.append({"type": "image_url", "image_url": {"url": data_url}})
            added += 1
    return parts if added else None


def _parse_json_reply(text: str) -> dict:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE)
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                obj = json.loads(m.group(0))
                return obj if isinstance(obj, dict) else {}
            except Exception:
                return {}
    return {}


def _normalized_key(value: str) -> str:
    return re.sub(r"[\s\-—－_]", "", value or "").upper()


def _name_matches(expected: str, recognized: str) -> bool:
    e, r = _normalized_key(expected), _normalized_key(recognized)
    return bool(e and r and e == r)


def _number_matches(expected: str, recognized: str) -> bool:
    e, r = _normalized_key(expected), _normalized_key(recognized)
    if not e:
        return True
    if not r:
        return False
    de = re.sub(r"\D", "", e)
    dr = re.sub(r"\D", "", r)
    if de and dr:
        return de[-20:] == dr[-20:]
    return e == r


def _check_result(qualification: OrgQualification, obj: dict) -> dict:
    recognized_name = str(obj.get("holder_name") or "")
    recognized_no = str(obj.get("certificate_no") or "")
    name_ok = _name_matches(qualification.holder_name, recognized_name)
    no_ok = _number_matches(qualification.certificate_no, recognized_no)
    checks = obj.get("checks")
    if not isinstance(checks, list):
        checks = []
    authenticity = str(obj.get("authenticity") or "unclear").lower()
    try:
        confidence = float(obj.get("confidence", 0))
    except (TypeError, ValueError):
        confidence = 0
    valid = (
        bool(obj.get("valid") is True)
        and authenticity == "authentic"
        and name_ok
        and no_ok
        and confidence >= 0.7
    )
    return {
        "valid": valid,
        "authenticity": authenticity,
        "confidence": round(max(0.0, min(1.0, confidence)), 2),
        "recognized_name": recognized_name[:64],
        "recognized_certificate_no": recognized_no[:64],
        "holder_name_match": bool(name_ok),
        "certificate_no_match": bool(no_ok),
        "checks": [x for x in checks if isinstance(x, dict)][:8],
        "reason": str(obj.get("reason") or "")[:255],
    }


async def run_ai_check(db: Session, qualification: OrgQualification) -> dict:
    """执行一次 AI 预检，结果持久化。无可用模型时失败但不阻断人工审核。"""
    qualification.ai_status = "pending"
    qualification.ai_reason = "AI 预检中"
    db.commit()
    db.refresh(qualification)

    endpoints = [
        ep for ep in llm_service.active_endpoints(db)
        if ep.get("support_image", True)
    ]
    if not endpoints:
        result = {
            "valid": False,
            "confidence": 0,
            "reason": "暂无支持图像输入的大模型，请管理员人工审核",
        }
        _save_result(db, qualification, result, status="failed", model="无可用模型")
        return result

    org = qualification.org
    user_text = (
        f"材料类型：{MATERIAL_TYPE_LABEL.get(qualification.material_type, '资质证明')}\n"
        f"组织名称：{org.name if org else ''}\n"
        f"组织类型：{org.org_type if org else ''}\n"
        f"申请人：{qualification.user.nickname if qualification.user else ''}\n"
        f"持有人姓名：{qualification.holder_name or '（未填写）'}\n"
        f"证书编号：{qualification.certificate_no or '（未填写）'}\n"
        f"发证机构：{qualification.issuing_organization or '（未填写）'}\n"
        f"发证日期：{qualification.issue_date or '（未填写）'}\n"
        "请识别材料并与上述关键字段核对，返回 JSON。"
    )
    parts = _build_content_parts(qualification, user_text)
    if not parts:
        result = {"valid": False, "confidence": 0, "reason": "材料图片读取失败，请重新上传"}
        _save_result(db, qualification, result, status="failed", model="本地读取")
        return result

    last_err: Exception | None = None
    for ep in endpoints:
        try:
            text = await llm_service.chat_complete(
                ep,
                messages=[{"role": "user", "content": parts}],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            result = _check_result(qualification, _parse_json_reply(text))
            status = "passed" if result["valid"] else "suspicious"
            llm_service.mark_success(db, ep.get("id") or 0)
            _save_result(db, qualification, result, status=status, model=ep.get("name") or ep.get("model") or "LLM")
            return result
        except Exception as e:  # noqa: BLE001
            last_err = e
            logger.warning("资质 AI 预检失败 [%s]：%s", ep.get("name"), e)
            llm_service.mark_failure(db, ep.get("id") or 0, str(e))

    result = {
        "valid": False,
        "confidence": 0,
        "reason": "AI 预检暂不可用，请管理员人工审核",
        "error": str(last_err or "")[:200],
    }
    _save_result(db, qualification, result, status="failed", model="调用失败")
    return result


def _save_result(
    db: Session,
    qualification: OrgQualification,
    result: dict,
    *,
    status: str,
    model: str,
) -> None:
    qualification.ai_status = status
    qualification.ai_confidence = int(round(float(result.get("confidence", 0)) * 100))
    qualification.ai_checks = json.dumps(result.get("checks", []), ensure_ascii=False)
    qualification.ai_reason = str(result.get("reason") or "")[:255]
    qualification.ai_checked_at = datetime.utcnow()
    qualification.ai_check_model = model[:128]
    db.commit()
    db.refresh(qualification)
