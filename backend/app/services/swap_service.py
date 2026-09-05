"""交换服务：以物换物的状态机 + 家长双确认。

状态流转（全部零金钱）：
  pending_parent  发起方家长未确认
      | 家长点确认 -> pending_peer
  pending_peer    接收方家长未确认
      | 家长点确认 -> accepted
  accepted        双方家长都点头，等线下当面交换
      | 双方家长点"交换完成" -> completed（结算咸鱼币）
  任一未完成状态 -> cancelled（发起方扣 2 枚）

安全约束：
  - 不能和自己交换（两个 item 的 owner 不同）
  - 只能用自己 on_shelf 状态的物品发起/接受
  - 已进入 swapping 的物品不能再次发起其它交换（防一物多换）
"""
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..config import SWAP_STATUSES
from ..models import Item, Swap, User
from ..services import coin_service
from ..services.wechat_service import notify_parent


def _require_on_shelf(item: Item) -> None:
    if item.status != "on_shelf":
        raise HTTPException(400, f"「{item.name}」当前状态是 {item.status}，无法发起交换")


def _validate_swap(db: Session, initiator_item_id: int, receiver_item_id: int) -> tuple[Item, Item]:
    if initiator_item_id == receiver_item_id:
        raise HTTPException(400, "不能用自己的物品和自己交换")
    initiator_item = db.get(Item, initiator_item_id)
    receiver_item = db.get(Item, receiver_item_id)
    if not initiator_item or not receiver_item:
        raise HTTPException(404, "物品不存在")
    if initiator_item.owner_id == receiver_item.owner_id:
        raise HTTPException(400, "不能和自己交换哦")
    _require_on_shelf(initiator_item)
    _require_on_shelf(receiver_item)
    return initiator_item, receiver_item


def create_swap(db: Session, initiator: User, initiator_item_id: int, receiver_item_id: int, note: str) -> Swap:
    initiator_item, receiver_item = _validate_swap(db, initiator_item_id, receiver_item_id)

    if initiator_item.owner_id != initiator.id:
        raise HTTPException(403, "只能用自己的闲置发起交换")
    if initiator_item.org_id != receiver_item.org_id:
        raise HTTPException(400, "只能交换同一组织内的闲置")
    if not initiator.active_org_id or initiator_item.org_id != initiator.active_org_id:
        raise HTTPException(400, "请先切换到物品所在的组织")

    # 防一物多换：任一物品已在进行中的交换，则拒绝
    active = (
        db.query(Swap)
        .filter(
            Swap.status.in_(["pending_parent", "pending_peer", "accepted"]),
            (Swap.initiator_item_id == initiator_item_id)
            | (Swap.initiator_item_id == receiver_item_id)
            | (Swap.receiver_item_id == initiator_item_id)
            | (Swap.receiver_item_id == receiver_item_id),
        )
        .first()
    )
    if active:
        raise HTTPException(400, "这些物品中有宝贝已在交换中，请先完成或取消现有交换")

    swap = Swap(
        initiator_item_id=initiator_item_id,
        receiver_item_id=receiver_item_id,
        note=note,
        status="pending_parent",
    )
    db.add(swap)
    db.flush()

    # 物品进入锁定状态
    initiator_item.status = "swapping"
    receiver_item.status = "swapping"
    db.flush()

    # 微信订阅消息：通知发起方家长确认
    notify_parent(
        db,
        parent_openid=initiator.parent_openid,
        title="交换请求待确认",
        body=f"您的孩子 {initiator.nickname} 想用「{initiator_item.name}」"
             f"交换「{receiver_item.name}」，请到 App 内确认。",
        swap_id=swap.id,
    )
    return swap


def parent_confirm(db: Session, swap: Swap, side: str) -> Swap:
    """side: 'initiator' / 'receiver' —— 前端根据当前用户是哪一方家长传入。"""
    if swap.status not in ("pending_parent", "pending_peer"):
        raise HTTPException(400, f"当前状态 {swap.status} 无法执行家长确认")

    if side == "initiator":
        if swap.initiator_parent_confirmed:
            raise HTTPException(400, "您已确认过，等待对方家长确认")
        swap.initiator_parent_confirmed = True
    elif side == "receiver":
        if swap.receiver_parent_confirmed:
            raise HTTPException(400, "已确认过")
        swap.receiver_parent_confirmed = True
    else:
        raise HTTPException(400, "side 参数错误")

    # 双方家长都点头 -> accepted（可线下交换）；否则退回 pending_peer 催另一方
    swap.status = (
        "accepted"
        if swap.initiator_parent_confirmed and swap.receiver_parent_confirmed
        else "pending_peer"
    )
    db.flush()

    if swap.status == "accepted":
        body = f"双方家长已同意「{swap.initiator_item.name}」⇄「{swap.receiver_item.name}」，请约定课间当面交换。"
        notify_parent(db, swap.initiator.parent_openid, "交换已确认", body, swap_id=swap.id)
        notify_parent(db, swap.receiver.parent_openid, "交换已确认", body, swap_id=swap.id)
    return swap


def parent_deny(db: Session, swap: Swap) -> Swap:
    """家长拒绝：直接取消，不扣咸鱼币（孩子不承担拒绝成本）。"""
    if swap.status in ("completed", "cancelled"):
        raise HTTPException(400, "交换已结束")
    swap.status = "cancelled"
    swap.cancelled_at = datetime.utcnow()
    swap.cancel_reason = "家长拒绝"
    # 解锁物品
    swap.initiator_item.status = "on_shelf"
    swap.receiver_item.status = "on_shelf"
    db.flush()
    return swap


def cancel_swap(db: Session, swap: Swap, operator: User, reason: str) -> Swap:
    if swap.status in ("completed", "cancelled"):
        raise HTTPException(400, "交换已结束")
    swap.status = "cancelled"
    swap.cancelled_at = datetime.utcnow()
    swap.cancel_reason = reason or "用户取消"
    swap.initiator_item.status = "on_shelf"
    swap.receiver_item.status = "on_shelf"
    db.flush()

    # 无故取消扣发起方 2 枚（约束随意发起）
    if operator.id == swap.initiator.id and swap.status == "cancelled":
        coin_service.charge_swap_cancel_penalty(db, swap.initiator, swap.id)
    return swap


def complete_swap(db: Session, swap: Swap, side: str) -> Swap:
    """家长点"交换完成"。双方都点完后，正式 completed 并结算咸鱼币。"""
    if swap.status != "accepted":
        raise HTTPException(400, "双方家长确认后才能完成交换")
    if side == "initiator":
        swap.initiator_parent_completed = True
    elif side == "receiver":
        swap.receiver_parent_completed = True
    else:
        raise HTTPException(400, "side 参数错误")

    if swap.initiator_parent_completed and swap.receiver_parent_completed:
        swap.status = "completed"
        swap.completed_at = datetime.utcnow()
        swap.initiator_item.status = "swapped"
        swap.receiver_item.status = "swapped"
        # 双方各 +10 咸鱼币
        coin_service.grant_swap_complete_reward(db, swap.initiator, swap.id)
        coin_service.grant_swap_complete_reward(db, swap.receiver, swap.id)
    db.flush()
    return swap


def swap_timeline(swap: Swap) -> list[dict]:
    """给前端的时间线渲染数据。"""
    steps = [
        {"key": "request", "title": "发起交换", "done": True, "time": swap.created_at},
        {"key": "initiator_parent", "title": "发起方家长确认", "done": swap.initiator_parent_confirmed, "time": None},
        {"key": "receiver_parent", "title": "接收方家长确认", "done": swap.receiver_parent_confirmed, "time": None},
        {
            "key": "offline",
            "title": "线下当面交换",
            "done": swap.status in ("completed",),
            "time": swap.completed_at,
        },
        {
            "key": "complete",
            "title": "双方点“交换完成”",
            "total": True,
            "done": swap.initiator_parent_completed and swap.receiver_parent_completed,
            "time": swap.completed_at,
        },
    ]
    for s in steps:
        if s.get("time") is not None:
            s["time"] = s["time"].strftime("%m-%d %H:%M")
        else:
            s.pop("time", None)
            s["time"] = ""
    return steps
