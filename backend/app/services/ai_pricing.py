"""AI 估值服务：给闲置物一个"参考枚数"。

两级推理：
1. **视觉大模型（可选）** —— 从数据库读取多条启用的 LLM 配置，按优先级
   用 OpenAI SDK 调用兼容网关；全部失败再回退规则引擎。
   无数据库配置时兼容 .env 单 Key。
2. **规则引擎（兜底）**：关键词 + 新旧折减系数，可解释、零成本、离线可跑。

对外统一返回：{ suggested_coins, source, explanation, confidence }。
"""
import base64
import json
import logging
import os
import re

from sqlalchemy.orm import Session

from ..config import (
    AI_PRICING_SOURCE,
    CONDITION_SCALE,
    SessionLocal,
    UPLOAD_DIR,
)
from ..services import llm_service
from ..services.category_service import fallback_map

logger = logging.getLogger("salted_fish.ai_pricing")

_FALLBACK_CATEGORIES = fallback_map()

_KEYWORDS = list(_FALLBACK_CATEGORIES)

COIN_MIN, COIN_MAX = 1, 15

_VISION_SYSTEM_PROMPT = (
    "你是一个专门给小学生闲置物品估值的中立助手。"
    "围绕「咸鱼币」——这是荣誉积分，不是钱，最大值不得超过 15。"
    "根据用户提供的物品照片(或文字)评估：类别、成色、建议咸鱼币枚数。"
    "请只返回 JSON，不要任何额外文字，格式："
    '{"coins": 整数, "condition": "细微挡位数(如 九成新)", "confidence": 0到1的小数, "note": "一句话中文说明"}'
)


def _match_category(name: str, category: str, categories: dict) -> str:
    if category in categories:
        return category
    for kw in _KEYWORDS:
        if kw in name:
            return kw
    return "其他"


def _match_condition(condition: str) -> int:
    for i, c in enumerate(CONDITION_SCALE):
        if c in condition:
            return i
    return 1


def _rule_estimate(name: str, category: str, description: str, condition: str,
                   categories: dict | None = None) -> dict:
    cats = categories or _FALLBACK_CATEGORIES
    cat = _match_category(name, category, cats)
    base, note = cats.get(cat, (2, "按类别参照"))
    cond_idx = _match_condition(condition)
    factor = 1.0 - 0.15 * cond_idx
    bonus = 1 if re.search(r"绝版|限量|全新未拆|未拆封|整套", f"{name} {description}") else 0
    suggested = max(COIN_MIN, min(COIN_MAX, round(base * factor) + bonus))
    explanation = (
        f"识别类别「{cat}」基准 {base} 枚，"
        f"新旧「{CONDITION_SCALE[cond_idx]}」折减系数 {factor:.2f}，"
        + (f"命中稀有关键词 +1 枚，" if bonus else "")
        + f"建议参考 {suggested} 枚咸鱼币（{note}）。"
    )
    return {
        "suggested_coins": suggested,
        "confidence": 0.55,
        "source": AI_PRICING_SOURCE,
        "explanation": explanation,
    }


def _to_data_url(path: str) -> str | None:
    fname = os.path.basename(path)
    ext = os.path.splitext(fname)[1].lstrip(".").lower() or "png"
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "webp": "image/webp", "gif": "image/gif"}.get(ext, "image/png")
    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
    except Exception as e:  # noqa: BLE001
        logger.warning("读取本地图片失败 %s: %s", path, e)
        return None
    return f"data:{mime};base64,{b64}"


def _build_content_parts(image_urls) -> list | None:
    content_parts = [
        {"type": "text", "text": _VISION_SYSTEM_PROMPT},
        {"type": "text",
         "text": "物品名称和描述会单独提供，请优先根据照片评估成色与枚数。返回 JSON。"},
    ]
    added = 0
    for url in image_urls:
        data_url = None
        if url.startswith("/uploads/"):
            local = os.path.join(UPLOAD_DIR, os.path.basename(url))
            data_url = _to_data_url(local) if os.path.exists(local) else None
        elif url.startswith("data:"):
            data_url = url
        elif url.startswith("http"):
            data_url = url
        if data_url:
            content_parts.append({"type": "image_url", "image_url": {"url": data_url}})
            added += 1
    if added == 0:
        return None
    return content_parts


async def _call_one_endpoint(endpoint: dict, content_parts: list) -> dict:
    text = await llm_service.chat_complete(
        endpoint,
        messages=[{"role": "user", "content": content_parts}],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    obj = _parse_json_reply(text)
    coins = int(obj.get("coins", 0))
    coins = max(COIN_MIN, min(COIN_MAX, coins))
    confidence = float(obj.get("confidence", 0.7))
    note = str(obj.get("note", "") or obj.get("condition", "") or "")
    label = endpoint.get("name") or endpoint.get("model")
    return {
        "suggested_coins": coins,
        "confidence": round(max(0.0, min(1.0, confidence)), 2),
        "source": f"vision:{label}",
        "explanation": (
            f"AI 视觉识别「{note}」，建议参考 {coins} 枚咸鱼币。"
            if note
            else f"AI 视觉识别，建议参考 {coins} 枚咸鱼币。"
        ),
        "_provider_id": endpoint.get("id") or 0,
    }


async def _visual_estimate(image_urls, db: Session | None = None) -> dict | None:
    content_parts = _build_content_parts(image_urls)
    if not content_parts:
        return None

    own_db = False
    if db is None:
        db = SessionLocal()
        own_db = True
    try:
        endpoints = [
            ep for ep in llm_service.active_endpoints(db)
            if ep.get("support_image", True)  # 仅挑选声明支持图像/多模态输入的模型
        ]
        if not endpoints:
            logger.warning("无可用的支持图像输入的 LLM 配置，回退规则引擎")
            return None
        last_err = None
        for ep in endpoints:
            try:
                result = await _call_one_endpoint(ep, content_parts)
                llm_service.mark_success(db, ep.get("id") or 0)
                result.pop("_provider_id", None)
                return result
            except Exception as e:  # noqa: BLE001
                last_err = e
                logger.warning("视觉估值失败 [%s]：%s", ep.get("name"), e)
                llm_service.mark_failure(db, ep.get("id") or 0, str(e))
        if last_err:
            logger.warning("全部 LLM 配置失败，回退规则引擎：%s", last_err)
        return None
    finally:
        if own_db:
            db.close()


def _parse_json_reply(text: str) -> dict:
    text = text.strip()
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


async def estimate_value(name, category, description, condition, image_urls=None,
                         categories=None, db: Session | None = None):
    """统一入口。image_urls 若提供且有可用 LLM，则优先视觉识别。"""
    if image_urls:
        vision = await _visual_estimate(image_urls, db=db)
        if vision and vision["suggested_coins"]:
            return vision
    return _rule_estimate(name, category, description, condition, categories)


async def probe_endpoint(endpoint: dict) -> dict:
    """连通性探测：发一条极简文本请求，不要求视觉。"""
    content = await llm_service.chat_complete(
        endpoint,
        messages=[{"role": "user", "content": "回复一个字：好"}],
        temperature=0,
        max_tokens=8,
    )
    return {"ok": True, "reply": str(content)[:80]}
