"""家长端路由：通知列表（订阅消息 mock 收件箱）+ 确认操作转发。

比赛演示时，家长手机上的微信订阅消息在本页模拟。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import get_db
from ..models import Swap
from ..schemas import Msg
from ..routers.auth import get_current_user
from ..services import swap_service, wechat_service

router = APIRouter(prefix="/parent", tags=["parent"])


def _user_by_parent_openid(db: Session, parent_openid: str):
    """演示辅助：家长 openid 反查孩子。真实场景由微信端身份体系承担。"""
    from ..models import User

    return db.query(User).filter(User.parent_openid == parent_openid).first()


@router.get("/notifications")
def notifications(token: str, db: Session = Depends(get_db)):
    """家长通知收件箱。token 是孩子的 token，取其 parent_openid 的消息。"""
    user = get_current_user(token, db)
    return {"notifications": wechat_service.list_notifications(db, user.parent_openid)}


@router.post("/notifications/{nid}/read", response_model=Msg)
def read_notification(nid: int, token: str, db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    row = wechat_service.mark_notifications_read(db, user.parent_openid, nid)
    if not row:
        raise HTTPException(404, "通知不存在")
    db.commit()
    return Msg(message="已读", data={"swap_id": row.swap_id})
