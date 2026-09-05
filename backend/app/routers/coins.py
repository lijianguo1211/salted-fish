"""咸鱼币 + 排行榜路由。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import COIN_NAME, COIN_RULES, get_db, LEADERBOARD_TOP_N
from ..models import CoinLedger
from ..schemas import CoinLedgerOut, CoinRuleOut
from ..routers.auth import get_current_user
from ..services import coin_service

router = APIRouter(prefix="/coins", tags=["coins"])


@router.get("/rules", response_model=list[CoinRuleOut])
def coin_rules():
    return COIN_RULES


@router.get("/ledger", response_model=list[CoinLedgerOut])
def my_ledger(token: str, db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    rows = (
        db.query(CoinLedger)
        .filter(CoinLedger.user_id == user.id)
        .order_by(CoinLedger.created_at.desc())
        .limit(50)
        .all()
    )
    return [r.to_dict() for r in rows]


@router.get("/leaderboard")
def leaderboard(token: str, school: str = "", db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    org_id = user.active_org_id or None
    data = coin_service.get_leaderboard(
        db, top_n=LEADERBOARD_TOP_N, school=school or None, org_id=org_id
    )
    return {"coin_name": COIN_NAME, "leaderboard": data, "org_id": org_id or 0}
