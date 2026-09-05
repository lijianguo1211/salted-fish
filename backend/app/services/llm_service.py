"""大模型配置：多厂商 / 多 Key，按优先级故障切换。"""
from datetime import datetime

from sqlalchemy.orm import Session

from ..config import (
    AI_VISION_API_KEY,
    AI_VISION_BASE_URL,
    AI_VISION_ENABLED,
    AI_VISION_MODEL,
)
from ..models import LlmProvider

KNOWN_VENDORS = (
    "openai",
    "deepseek",
    "siliconflow",
    "moonshot",
    "zhipu",
    "qwen",
    "groq",
    "custom",
)

VENDOR_PRESETS = {
    "openai": {"label": "OpenAI", "base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
    "deepseek": {"label": "DeepSeek", "base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat"},
    "siliconflow": {"label": "硅基流动", "base_url": "https://api.siliconflow.cn/v1", "model": "Qwen/Qwen2.5-VL-72B-Instruct"},
    "moonshot": {"label": "月之暗面", "base_url": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k"},
    "zhipu": {"label": "智谱", "base_url": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-4v-flash"},
    "qwen": {"label": "通义千问", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-vl-plus"},
    "groq": {"label": "Groq", "base_url": "https://api.groq.com/openai/v1", "model": "llama-3.2-11b-vision-preview"},
    "custom": {"label": "自定义", "base_url": "https://example.com/v1", "model": "gpt-4o-mini"},
}


def list_providers(db: Session, *, active_only: bool = False) -> list[LlmProvider]:
    q = db.query(LlmProvider)
    if active_only:
        q = q.filter(LlmProvider.is_active == True)  # noqa: E712
    return q.order_by(LlmProvider.sort_order.asc(), LlmProvider.id.asc()).all()


def active_endpoints(db: Session) -> list[dict]:
    """返回可调用的 endpoint 列表（DB 优先；无启用项时回退 .env）。"""
    rows = [p for p in list_providers(db, active_only=True) if p.api_key and p.base_url]
    if rows:
        return [
            {
                "id": p.id,
                "name": p.name,
                "vendor": p.vendor,
                "base_url": p.base_url.rstrip("/"),
                "api_key": p.api_key,
                "model": p.model,
                "timeout_sec": p.timeout_sec or 30,
            }
            for p in rows
        ]
    # 兼容旧 .env 单 Key
    if AI_VISION_ENABLED and AI_VISION_API_KEY:
        return [
            {
                "id": 0,
                "name": "env-default",
                "vendor": "env",
                "base_url": AI_VISION_BASE_URL.rstrip("/"),
                "api_key": AI_VISION_API_KEY,
                "model": AI_VISION_MODEL,
                "timeout_sec": 30,
            }
        ]
    return []


def mark_success(db: Session, provider_id: int) -> None:
    if not provider_id:
        return
    p = db.get(LlmProvider, provider_id)
    if not p:
        return
    p.last_ok_at = datetime.utcnow()
    p.last_error = ""
    p.fail_count = 0
    db.commit()


def mark_failure(db: Session, provider_id: int, error: str) -> None:
    if not provider_id:
        return
    p = db.get(LlmProvider, provider_id)
    if not p:
        return
    p.last_error = (error or "")[:255]
    p.fail_count = (p.fail_count or 0) + 1
    db.commit()
