"""自包含的签名令牌（HMAC-SHA256），本质是迷你 JWT，仅用标准库实现。

无需第三方依赖（不引入 PyJWT）。格式：base64(header).base64(payload).signature
适用于"真实微信登录"下给 userId 签发有签名的会话凭证；DEMO 模式仍用 demo-token。
"""
import base64
import hashlib
import hmac
import json
import os
import time

_SECRET = os.environ.get("SALTED_FISH_TOKEN_SECRET", "dev-secret-change-me-in-prod")
_EXPIRE = 7 * 24 * 3600  # 7 天


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _sign(data: str) -> str:
    return _b64url(hmac.new(_SECRET.encode(), data.encode(), hashlib.sha256).digest())


def create_token(user_id: int) -> str:
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url(json.dumps({"uid": user_id, "exp": int(time.time()) + _EXPIRE}).encode())
    signing = f"{header}.{payload}"
    return f"{signing}.{_sign(signing)}"


def parse_token(token: str, now: int | None = None):
    """返回 (user_id) 或抛 ValueError（签名错误/过期/格式错误）。"""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("bad token")
    header, payload, sig = parts
    signing = f"{header}.{payload}"
    if not hmac.compare_digest(_sign(signing), sig):
        raise ValueError("bad signature")
    data = json.loads(_b64url_decode(payload))
    exp = data.get("exp", 0)
    if now is None:
        now = int(time.time())
    if now > exp:
        raise ValueError("expired")
    return int(data["uid"])