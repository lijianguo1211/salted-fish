"""微信生态服务：订阅消息（家长确认通知）。

比赛演示：WECHAT_MOCK=1 时不真正调微信接口，只落库 + 打日志，
演示时把 mock 消息直接展示在"家长端模拟器"页面，3 分钟路演够用。
真实上线时把 send_subscribe_message 换成 HTTP 调用即可。
"""
import logging
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import Session

from ..config import WECHAT_MOCK
from ..models import Base

logger = logging.getLogger("salted_fish.wechat")


class WechatNotification(Base):
    __tablename__ = "wechat_notifications"

    id = Column(Integer, primary_key=True, index=True)
    parent_openid = Column(String(64), index=True)
    title = Column(String(64), default="")
    body = Column(Text, default="")
    swap_id = Column(Integer, index=True, default=0)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "parent_openid": self.parent_openid,
            "title": self.title,
            "body": self.body,
            "swap_id": self.swap_id,
            "is_read": self.is_read,
            "created_at": self.created_at.strftime("%m-%d %H:%M") if self.created_at else "",
        }


def notify_parent(db: Session, parent_openid: str, title: str, body: str, swap_id: int = 0):
    """给家长发订阅消息。mock 模式落库；真实模式调微信接口（占位）。"""
    if not parent_openid:
        logger.info("[wechat-mock] 无家长 openid，跳过：%s", title)
        return None
    row = WechatNotification(
        parent_openid=parent_openid,
        title=title,
        body=body,
        swap_id=swap_id,
    )
    db.add(row)
    db.flush()
    if WECHAT_MOCK:
        logger.info("[wechat-mock] %s | %s | %s", parent_openid, title, body)
    else:
        # 真实模式：调微信订阅消息接口（占位，比赛后接）
        logger.info("[wechat] TODO 真实订阅消息 openid=%s title=%s", parent_openid, title)
    return row


def mark_notifications_read(db: Session, parent_openid: str, notification_id: int):
    row = db.query(WechatNotification).filter(
        WechatNotification.id == notification_id,
        WechatNotification.parent_openid == parent_openid,
    ).first()
    if row:
        row.is_read = True
        db.flush()
    return row


def list_notifications(db: Session, parent_openid: str):
    rows = (
        db.query(WechatNotification)
        .filter(WechatNotification.parent_openid == parent_openid)
        .order_by(WechatNotification.created_at.desc())
        .limit(50)
        .all()
    )
    return [r.to_dict() for r in rows]
