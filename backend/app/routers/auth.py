"""认证：微信登录。

两种模式：
- DEMO_MODE=1（比赛演示）：body.code 直接作昵称/标识，签发 `demo-token-{id}`，无需真实微信。
- 真实模式：用 wx.login 的 code 调 jscode2session 换取 openid，再签 HMAC 签名令牌。

令牌：
  - demo 模式：`demo-token-{user_id}`（明文，仅演示用）
  - 真实模式：services.token 的 HMAC-SHA256 签名令牌（格式同 JWT）
"""
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import ADMIN_OPENIDS, DEMO_MODE, WECHAT_APPID, WECHAT_APP_SECRET, get_db
from ..models import User
from ..schemas import LoginRequest, UserOut
from ..services import coin_service
from ..services import token as token_svc

router = APIRouter(prefix="/auth", tags=["auth"])

TOKEN_PREFIX = "demo-token-"
logger = logging.getLogger("salted_fish.auth")


class TokenOut(BaseModel):
    token: str
    user: UserOut


def get_current_user(token: str, db: Session) -> User:
    if token.startswith(TOKEN_PREFIX):
        # DEMO 令牌：demo-token-{user_id}
        try:
            user_id = int(token[len(TOKEN_PREFIX):])
        except ValueError:
            raise HTTPException(401, "登录凭证无效")
        user = db.get(User, user_id)
    else:
        # 真实签名令牌
        try:
            user_id = token_svc.parse_token(token)
        except ValueError:
            raise HTTPException(401, "登录凭证无效或已过期")
        user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "用户不存在或已停用")
    return user


def make_token(user_id: int) -> str:
    if DEMO_MODE:
        return f"{TOKEN_PREFIX}{user_id}"
    return token_svc.create_token(user_id)


def _upsert_user(db: Session, openid: str, parent_openid: str,
                 nickname: str, grade_class: str, school: str) -> User:
    # 在 ADMIN_OPENIDS 名单内的 openid 或昵称自动成为管理员
    # （真实模式用 openid，演示模式 nickname 即 openid，两种都能命中）
    is_admin = openid in ADMIN_OPENIDS or nickname in ADMIN_OPENIDS
    user = db.query(User).filter(User.openid == openid).first()
    if not user:
        user = User(
            openid=openid,
            parent_openid=parent_openid,
            nickname=nickname or "小咸鱼",
            role="admin" if is_admin else "student",
            school=school or "示范小学",
            grade_class=grade_class or "三年级2班",
        )
        db.add(user)
        db.flush()
        coin_service.grant_register_bonus(db, user)
    else:
        if nickname:
            user.nickname = nickname
        if school:
            user.school = school
        if grade_class:
            user.grade_class = grade_class
        # 已在名单内则始终维持 admin 角色
        if is_admin:
            user.role = "admin"
    return user


@router.post("/login", response_model=TokenOut)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    if DEMO_MODE:
        openid = body.code or f"demo-{body.nickname}"
        parent_openid = f"parent-{openid}"
        user = _upsert_user(db, openid, parent_openid, body.nickname,
                              body.grade_class, body.school)
        db.commit()
        return TokenOut(token=make_token(user.id), user=user.to_dict())

    # ---- 真实微信登录（jscode2session） ----
    if not WECHAT_APPID or not WECHAT_APP_SECRET:
        raise HTTPException(503, "真实模式需要配置 WECHAT_APPID / WECHAT_APP_SECRET")
    if not body.code:
        raise HTTPException(400, "缺少 wx.login 的 code")

    try:
        resp = httpx.get(
            "https://api.weixin.qq.com/sns/jscode2session",
            params={
                "appid": WECHAT_APPID,
                "secret": WECHAT_APP_SECRET,
                "js_code": body.code,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
        data = resp.json()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"微信登录服务暂时不可用：{e}")

    if data.get("errcode"):
        raise HTTPException(401, f"微信登录失败：{data.get('errmsg', '')}")
    openid = data["openid"]
    user = _upsert_user(db, openid, f"wxparent-{openid}",
                          body.nickname, body.grade_class, body.school)
    db.commit()
    return TokenOut(token=make_token(user.id), user=user.to_dict())


@router.get("/me", response_model=UserOut)
def me(token: str, db: Session = Depends(get_db)):
    return get_current_user(token, db).to_dict()