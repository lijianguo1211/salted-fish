"""AI 内容合规检测：拦截不宜上架、不利于学生的闲置。

开启条件（后台 AppSetting：ai_moderation_enabled=1）：
  - 上架 / 改关键信息时必须过检；
  - 优先调用已启用的文本/多模态 LLM；
  - 全部 LLM 失败时用本地关键词兜底（开启状态下不放行未知风险）。

返回：{ allowed, risk, labels, reason, source }
"""
from __future__ import annotations

import json
import logging
import re

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..services import llm_service
from ..services import org_service

logger = logging.getLogger("salted_fish.ai_moderation")

SETTING_AI_PRICING = "ai_pricing_enabled"
SETTING_AI_MODERATION = "ai_moderation_enabled"

# 本地硬拦截关键词（开启合规时 LLM 不可用也生效）
_BLOCK_KEYWORDS = (
    "香烟", "烟丝", "电子烟", "酒精", "白酒", "啤酒", "鸦片", "大麻", "冰毒", "摇头丸",
    "枪支", "子弹", "炸药", "雷管", "管制刀具", "匕首",
    "色情", "成人用品", "避孕套", "情趣",
    "赌博", "六合彩", "彩票代购",
    "自杀", "自残",
)

_SYSTEM_PROMPT = (
    "你是面向中小学生「以物换物」平台的内容审核员。"
    "平台只允许适龄闲置交换（文具、绘本、玩具、卡牌、体育用品等），禁止不利于学生身心健康或违法违规物品。"
    "请根据名称、类别、描述、成色与（如有）照片判断是否允许上架。"
    "明确禁止：色情低俗、暴力血腥、枪支刀具弹药、烟酒毒品、赌博诈骗、仇恨歧视、政治敏感、"
    "危险化学品、成人用品、现金买卖/有偿转让引导、及其他不利于未成年人的内容。"
    "请只返回 JSON，不要其它文字，格式："
    '{"allowed": true或false, "risk": "low|medium|high", "labels": ["标签"], "reason": "一句话中文说明"}'
)


def is_pricing_enabled(db: Session) -> bool:
    raw = org_service.get_setting(db, SETTING_AI_PRICING, "1")
    return str(raw).strip() not in ("0", "false", "False", "off", "OFF")


def is_moderation_enabled(db: Session) -> bool:
    raw = org_service.get_setting(db, SETTING_AI_MODERATION, "0")
    return str(raw).strip() in ("1", "true", "True", "on", "ON")


def get_ai_settings(db: Session) -> dict:
    return {
        "ai_pricing_enabled": is_pricing_enabled(db),
        "ai_moderation_enabled": is_moderation_enabled(db),
    }


def set_ai_settings(
    db: Session,
    *,
    ai_pricing_enabled: bool | None = None,
    ai_moderation_enabled: bool | None = None,
) -> dict:
    if ai_pricing_enabled is not None:
        org_service.set_setting(db, SETTING_AI_PRICING, "1" if ai_pricing_enabled else "0")
    if ai_moderation_enabled is not None:
        org_service.set_setting(db, SETTING_AI_MODERATION, "1" if ai_moderation_enabled else "0")
    db.flush()
    return get_ai_settings(db)


def _parse_json_reply(text: str) -> dict:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE)
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return {}
    return {}


def _keyword_check(name: str, description: str, category: str) -> dict | None:
    blob = f"{name} {description} {category}"
    hits = [kw for kw in _BLOCK_KEYWORDS if kw in blob]
    if not hits:
        return None
    return {
        "allowed": False,
        "risk": "high",
        "labels": hits[:5],
        "reason": f"包含不宜上架内容（{hits[0]}），请更换物品",
        "source": "keyword",
    }


def _build_user_prompt(name: str, category: str, description: str, condition: str) -> str:
    return (
        f"物品名称：{name}\n"
        f"类别：{category}\n"
        f"成色：{condition or '未知'}\n"
        f"描述：{description or '（无）'}\n"
        "请审核是否允许上架，并返回 JSON。"
    )


async def _call_text_endpoint(endpoint: dict, prompt: str) -> dict:
    text = await llm_service.chat_complete(
        endpoint,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    obj = _parse_json_reply(text)
    allowed = bool(obj.get("allowed", False))
    risk = str(obj.get("risk") or ("low" if allowed else "high")).lower()
    if risk not in ("low", "medium", "high"):
        risk = "high" if not allowed else "low"
    labels = obj.get("labels") or []
    if not isinstance(labels, list):
        labels = [str(labels)]
    reason = str(obj.get("reason") or ("通过合规检测" if allowed else "未通过合规检测"))
    return {
        "allowed": allowed,
        "risk": risk,
        "labels": [str(x) for x in labels][:8],
        "reason": reason[:200],
        "source": f"llm:{endpoint.get('name') or endpoint.get('model')}",
    }


async def moderate_item(
    db: Session,
    *,
    name: str,
    category: str,
    description: str = "",
    condition: str = "",
    image_urls: list[str] | None = None,
) -> dict:
    """执行合规检测。关闭开关时直接放行。"""
    if not is_moderation_enabled(db):
        return {
            "allowed": True,
            "risk": "low",
            "labels": [],
            "reason": "未开启 AI 合规检测",
            "source": "disabled",
        }

    hit = _keyword_check(name, description or "", category or "")
    if hit:
        return hit

    prompt = _build_user_prompt(name, category or "", description or "", condition or "")
    # 文本模型优先；若仅有多模态也可走文本接口
    endpoints = [
        ep for ep in llm_service.active_endpoints(db)
        if ep.get("support_text", True) or ep.get("support_image", False)
    ]
    if not endpoints:
        # 开启后无可用模型：拒绝上架，避免漏检
        return {
            "allowed": False,
            "risk": "high",
            "labels": ["no_llm"],
            "reason": "已开启 AI 合规检测，但暂无可用大模型，请稍后重试或联系管理员",
            "source": "no_llm",
        }

    last_err = None
    for ep in endpoints:
        try:
            result = await _call_text_endpoint(ep, prompt)
            llm_service.mark_success(db, ep.get("id") or 0)
            # medium/high 且模型判不允许才拦；若模型给 high 但 allowed=true，仍信任 allowed
            return result
        except Exception as e:  # noqa: BLE001
            last_err = e
            logger.warning("合规检测失败 [%s]：%s", ep.get("name"), e)
            llm_service.mark_failure(db, ep.get("id") or 0, str(e))

    logger.warning("全部 LLM 合规检测失败：%s", last_err)
    return {
        "allowed": False,
        "risk": "high",
        "labels": ["llm_error"],
        "reason": "AI 合规检测暂时不可用，请稍后重试",
        "source": "error",
    }


async def assert_item_allowed(
    db: Session,
    *,
    name: str,
    category: str,
    description: str = "",
    condition: str = "",
    image_urls: list[str] | None = None,
) -> dict:
    """开启检测时若不通过则抛 HTTP 400。"""
    result = await moderate_item(
        db,
        name=name,
        category=category,
        description=description,
        condition=condition,
        image_urls=image_urls,
    )
    if not result.get("allowed", False):
        raise HTTPException(400, result.get("reason") or "未通过 AI 合规检测，无法上架")
    return result
