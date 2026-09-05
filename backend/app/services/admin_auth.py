"""独立后台管理员账号的密码哈希与令牌签发。

- 密码：PBKDF2-HMAC-SHA256（stdlib，无第三方依赖），带随机盐。
- 令牌：`admin-web-{signed}`，HMAC-SHA256 签名，可被 admin.py 的 get_current_admin 识别
  （与小程序 openid 令牌分开，互不占用）。
"""
import base64
import hashlib
import hmac
import os
import time

from fastapi import HTTPException

from ..config import TOKEN_EXPIRE_HOURS

# 与小程序令牌共用同一密钥来源（保持一致性，避免新配一个 env）
_SECRET = os.environ.get("SALTED_FISH_TOKEN_SECRET", "dev-secret-change-me-in-prod")
_EXPIRE = (TOKEN_EXPIRE_HOURS or 24) * 3600

# 令牌前缀，便于 admin router 区分"小程序管理员"与"独立后台管理员"
ADMIN_WEB_TOKEN_PREFIX = "admin-web-"


def hash_password(password: str, salt: bytes | None = None) -> str:
    """返回 `pbkdf2$salt$hash` 格式。"""
    salt = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return "pbkdf2$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_b64, hash_b64 = stored.split("$")
        salt = base64.b64decode(salt_b64)
        expect = base64.b64decode(hash_b64)
    except Exception:
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return hmac.compare_digest(dk, expect)


def create_admin_token(admin_id: int) -> str:
    """签发独立后台管理员令牌。"""
    exp = int(time.time()) + _EXPIRE
    payload = f"{admin_id}.{int(time.time())}.{exp}"
    sig = hmac.new(_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    raw = base64.urlsafe_b64encode((payload + "." + sig).encode()).decode()
    return ADMIN_WEB_TOKEN_PREFIX + raw


def parse_admin_token(token: str) -> int:
    """校验独立后台令牌，返回 admin id；失败抛 401。"""
    if not token.startswith(ADMIN_WEB_TOKEN_PREFIX):
        raise HTTPException(401, "非后台管理员令牌")
    raw = token[len(ADMIN_WEB_TOKEN_PREFIX):]
    try:
        decoded = base64.urlsafe_b64decode(raw.encode()).decode()
        payload, sig = decoded.rsplit(".", 1)
        admin_id, issued, expires = payload.split(".")
        expect = int(admin_id)
    except Exception:
        raise HTTPException(401, "令牌无效")
    check = hmac.new(_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(check, sig):
        raise HTTPException(401, "令牌签名无效")
    if int(time.time()) > int(expires):
        raise HTTPException(401, "登录已过期，请重新登录")
    return expect