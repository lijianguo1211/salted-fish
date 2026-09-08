"""认证：微信登录 + 完善资料。

流程：微信授权登录 → 加入/创建组织 → 完善用户信息 → 进鱼塘。

两种模式：
- DEMO_MODE=1：body.code 作 openid 标识（前端存演示设备 ID），无需真实微信。
- 真实模式：wx.login code → jscode2session → openid。
"""
import logging
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import ADMIN_OPENIDS, DEMO_MODE, WECHAT_APPID, WECHAT_APP_SECRET, get_db
from ..models import User
from ..schemas import LoginRequest, ProfileUpdate, UserOut
from ..services import coin_service
from ..services import token as token_svc
from ..services import rate_limit

router = APIRouter(prefix="/auth", tags=["auth"])

TOKEN_PREFIX = "demo-token-"
logger = logging.getLogger("salted_fish.auth")


class TokenOut(BaseModel):
    token: str
    user: UserOut


def resolve_token(token: str = "", authorization: str | None = None) -> str:
    """优先读 Authorization: Bearer，其次 query/form 的 token。"""
    if authorization:
        raw = authorization.strip()
        if raw.lower().startswith("bearer "):
            raw = raw[7:].strip()
        if raw:
            return raw
    return (token or "").strip()


def get_current_user(token: str, db: Session) -> User:
    token = (token or "").strip()
    if not token:
        raise HTTPException(401, "未登录")
    if token.startswith(TOKEN_PREFIX):
        try:
            user_id = int(token[len(TOKEN_PREFIX):])
        except ValueError:
            raise HTTPException(401, "登录凭证无效")
        user = db.get(User, user_id)
    else:
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
                 nickname: str = "", grade_class: str = "", school: str = "") -> User:
    is_admin = openid in ADMIN_OPENIDS or (nickname and nickname in ADMIN_OPENIDS)
    user = db.query(User).filter(User.openid == openid).first()
    if not user:
        user = User(
            openid=openid,
            parent_openid=parent_openid,
            nickname=(nickname or "").strip() or "小咸鱼",
            role="admin" if is_admin else "student",
            school=(school or "").strip(),
            grade_class=(grade_class or "").strip(),
            profile_completed=False,
        )
        db.add(user)
        db.flush()
        coin_service.grant_register_bonus(db, user)
    else:
        # 登录不再覆盖资料；资料走 /auth/profile
        if is_admin:
            user.role = "admin"
        elif openid in ADMIN_OPENIDS:
            user.role = "admin"
        # 旧账号迁移后可能缺标志：已有真实昵称则视为已完善
        if (
            not user.profile_completed
            and (user.nickname or "").strip()
            and user.nickname != "小咸鱼"
        ):
            user.profile_completed = True
    return user


@router.post("/login", response_model=TokenOut)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    rate_limit.check("login", rate_limit.client_ip(request), max_hits=12, window_sec=60)
    if DEMO_MODE:
        # 演示：code 为设备/会话标识；无 code 时生成临时标识（不推荐，前端应固定存一份）
        code = (body.code or "").strip() or f"demo-{uuid.uuid4().hex[:12]}"
        openid = code if code.startswith("demo-") else f"demo-{code}"
        parent_openid = f"parent-{openid}"
        user = _upsert_user(db, openid, parent_openid)
        db.commit()
        db.refresh(user)
        return TokenOut(token=make_token(user.id), user=user.to_dict())

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
    user = _upsert_user(db, openid, f"wxparent-{openid}")
    db.commit()
    db.refresh(user)
    return TokenOut(token=make_token(user.id), user=user.to_dict())


@router.get("/me", response_model=UserOut)
def me(token: str, db: Session = Depends(get_db)):
    return get_current_user(token, db).to_dict()


@router.put("/profile", response_model=UserOut)
def update_profile(body: ProfileUpdate, token: str, db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    nickname = body.nickname.strip()
    grade_class = body.grade_class.strip()
    school = body.school.strip()
    if not nickname or nickname == "小咸鱼" or nickname.lower().startswith("demo-"):
        raise HTTPException(400, "请填写真实昵称")
    if not grade_class:
        raise HTTPException(400, "请填写真实班级")
    if not school:
        raise HTTPException(400, "请填写真实学校")
    user.nickname = nickname
    user.grade_class = grade_class
    user.school = school
    user.profile_completed = True
    # 演示管理员：昵称命中名单则升为 admin
    if nickname in ADMIN_OPENIDS or user.openid in ADMIN_OPENIDS:
        user.role = "admin"
    db.commit()
    db.refresh(user)
    return user.to_dict()
