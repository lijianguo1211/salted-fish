"""咸鱼币服务：积分发放/扣除 + 流水台账。

合规红线（写进代码注释与 PRD）：
  咸鱼币是行为积分，不是货币 —— 不可转账、不可兑现金、不可购买任何商品。
  所有变动都由系统规则触发，绝不开放用户间转移接口。
  未来“本子/笔/橡皮擦”兑换属于运营方单方赠品计划（线下发放），
  上线前需家长知情同意，且不得与任何支付行为挂钩。
"""
from sqlalchemy.orm import Session

from ..config import (
    COIN_INITIAL_BALANCE,
    COIN_NAME,
    COIN_PENALTY_CANCEL_SWAP,
    COIN_REWARD_COMPLETE_SWAP,
    COIN_REWARD_LIST_ITEM,
)
from ..models import CoinLedger, User

# 幂等保护：同一 (user, source_type, source_id) 只发一次
LEDGER_SOURCES = {
    "register": "注册欢迎礼",
    "list_item": "上架闲置",
    "swap_complete": "完成交换",
    "swap_cancel": "取消交换",
}


def _grant(db: Session, user: User, delta: int, source_type: str, source_id: int, note: str) -> None:
    if delta == 0:
        return
    exists = (
        db.query(CoinLedger)
        .filter(
            CoinLedger.user_id == user.id,
            CoinLedger.source_type == source_type,
            CoinLedger.source_id == source_id,
        )
        .first()
    )
    if exists:
        return  # 已发放，幂等跳过

    user.coin_balance = (user.coin_balance or 0) + delta
    ledger = CoinLedger(
        user_id=user.id,
        delta=delta,
        balance_after=user.coin_balance,
        source_type=source_type,
        source_id=source_id,
        note=note,
    )
    db.add(ledger)
    db.flush()


def grant_register_bonus(db: Session, user: User) -> None:
    _grant(db, user, COIN_INITIAL_BALANCE, "register", user.id, "注册欢迎礼")


def grant_list_item_reward(db: Session, user: User, item_id: int) -> None:
    _grant(db, user, COIN_REWARD_LIST_ITEM, "list_item", item_id, "上架闲置")


def grant_swap_complete_reward(db: Session, user: User, swap_id: int) -> None:
    _grant(db, user, COIN_REWARD_COMPLETE_SWAP, "swap_complete", swap_id, "交换完成，双方各 +10")


def charge_swap_cancel_penalty(db: Session, user: User, swap_id: int) -> None:
    _grant(db, user, -COIN_PENALTY_CANCEL_SWAP, "swap_cancel", swap_id, "无故取消交换")


def get_leaderboard(db: Session, top_n: int = 50, school: str = "", org_id: int | None = None):
    from ..models import OrgMembership

    q = db.query(User).filter(User.is_active == True)  # noqa: E712
    if org_id:
        q = q.filter(User.id.in_(db.query(OrgMembership.user_id).filter(
            OrgMembership.org_id == org_id, OrgMembership.status == "active"
        )))
    elif school:
        q = q.filter(User.school == school)
    users = (
        q.order_by(User.coin_balance.desc(), User.id.asc())
        .limit(top_n)
        .all()
    )
    return [
        {
            "rank": i + 1,
            "id": u.id,
            "nickname": u.nickname,
            "grade_class": u.grade_class,
            "coin_balance": u.coin_balance,
            "avatar": u.avatar,
        }
        for i, u in enumerate(users)
    ]
