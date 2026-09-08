"""独立后台管理员登录（邮箱 + 密码）。

安全设计：
- 前端先 GET /admin-auth/public-key 拿 RSA 公钥；
- 用公钥把密码做 RSA-OAEP(SHA-256) 加密后 base64 传后端（`encrypted_password`）；
- 后端用私钥解出明文密码，再走 PBKDF2 校验 —— 密码不明文过网，库中只存哈希。
与小程序 openid 登录完全分离：管理员账号存 admin_users 表。
"""
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import get_db
from ..models import AdminUser
from ..services import admin_crypto
from ..services import rate_limit
from ..services.admin_auth import create_admin_token, parse_admin_token, verify_password

router = APIRouter(prefix="/admin-auth", tags=["admin-auth"])

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AdminLoginIn(BaseModel):
    email: str
    encrypted_password: str  # RSA-OAEP 公钥加密后的密码（base64）


class AdminLoginOut(BaseModel):
    token: str
    admin: dict


@router.get("/public-key")
def public_key():
    """返回 RSA 公钥（SPKI PEM），供前端加密密码。"""
    return {
        "public_key": admin_crypto.public_key_pem(),
        "algorithm": "RSA-OAEP-SHA256",
    }


@router.post("/login", response_model=AdminLoginOut)
def admin_login(body: AdminLoginIn, request: Request, db: Session = Depends(get_db)):
    rate_limit.check("admin-login", rate_limit.client_ip(request), max_hits=8, window_sec=60)
    email = body.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "邮箱格式不正确")

    # 解密前端传来的 RSA 密文 → 明文密码
    try:
        password = admin_crypto.decrypt_password(body.encrypted_password)
    except ValueError as e:
        raise HTTPException(400, f"密码解密失败：{e}") from e

    admin = db.query(AdminUser).filter(AdminUser.email == email).first()
    if not admin or not admin.is_active or not verify_password(password, admin.password_hash):
        raise HTTPException(401, "邮箱或密码错误")
    return {"token": create_admin_token(admin.id), "admin": admin.to_dict()}


@router.get("/me")
def admin_me(token: str = "", db: Session = Depends(get_db)):
    admin_id = parse_admin_token(token)
    admin = db.get(AdminUser, admin_id)
    if not admin or not admin.is_active:
        raise HTTPException(401, "管理员不存在或已停用")
    return {"ok": True, "admin": admin.to_dict()}