"""交换路由：发起、家长确认/拒绝、取消、完成、我的交换列表、详情时间线。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import get_db
from ..models import Swap, User
from ..schemas import Msg, SwapAction, SwapCreate, SwapOut
from ..routers.auth import get_current_user
from ..services import swap_service

router = APIRouter(prefix="/swaps", tags=["swaps"])


@router.post("", response_model=SwapOut)
def create_swap(body: SwapCreate, token: str, db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    swap = swap_service.create_swap(
        db, user, body.initiator_item_id, body.receiver_item_id, body.note
    )
    db.commit()
    db.refresh(swap)
    return swap.to_dict()


@router.get("", response_model=list[SwapOut])
def list_my_swaps(token: str, status: str = "", db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    q = db.query(Swap).filter(
        (Swap.initiator_item.has(owner_id=user.id))
        | (Swap.receiver_item.has(owner_id=user.id))
    )
    if status:
        q = q.filter(Swap.status == status)
    swaps = q.order_by(Swap.created_at.desc()).limit(50).all()
    return [s.to_dict() for s in swaps]


@router.get("/{swap_id}", response_model=SwapOut)
def get_swap(swap_id: int, token: str, db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    swap = db.get(Swap, swap_id)
    if not swap:
        raise HTTPException(404, "交换不存在")
    if user.id not in (swap.initiator.id, swap.receiver.id):
        raise HTTPException(403, "只能查看自己的交换")
    return swap.to_dict()


@router.post("/{swap_id}/actions", response_model=SwapOut)
def swap_action(swap_id: int, body: SwapAction, token: str, db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    swap = db.get(Swap, swap_id)
    if not swap:
        raise HTTPException(404, "交换不存在")
    if user.id not in (swap.initiator.id, swap.receiver.id):
        raise HTTPException(403, "只能操作自己的交换")

    side = "initiator" if user.id == swap.initiator.id else "receiver"

    if body.action == "parent_confirm":
        swap = swap_service.parent_confirm(db, swap, side)
    elif body.action == "parent_deny":
        swap = swap_service.parent_deny(db, swap)
    elif body.action == "cancel":
        swap = swap_service.cancel_swap(db, swap, user, body.reason)
    elif body.action == "complete":
        swap = swap_service.complete_swap(db, swap, side)
    else:
        raise HTTPException(400, f"未知操作 {body.action}")

    db.commit()
    db.refresh(swap)
    return swap.to_dict()


@router.get("/{swap_id}/timeline")
def timeline(swap_id: int, token: str, db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    swap = db.get(Swap, swap_id)
    if not swap:
        raise HTTPException(404, "交换不存在")
    if user.id not in (swap.initiator.id, swap.receiver.id):
        raise HTTPException(403, "只能查看自己的交换")
    return {"steps": swap_service.swap_timeline(swap)}
