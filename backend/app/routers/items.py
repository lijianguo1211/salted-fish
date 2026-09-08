"""物品路由：上架（AI 定价建议）、列表、我的、详情、下架、举报。"""
from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request
from sqlalchemy.orm import Session

from ..config import REPORT_REASONS, get_db
from ..models import Item, Report
from ..schemas import AIPricingIn, AIPricingOut, ItemCreate, ItemOut, ItemUpdate, Msg, ReportCreate
from ..routers.auth import get_current_user, resolve_token
from ..services import coin_service
from ..services.ai_pricing import estimate_value
from ..services import ai_moderation
from ..services import category_service
from ..services import org_service
from ..services import rate_limit

router = APIRouter(prefix="/items", tags=["items"])


async def _estimate_for_item(db: Session, name, category, description, condition, image_urls=None):
    images = image_urls if ai_moderation.is_pricing_enabled(db) else None
    return await estimate_value(
        name, category, description, condition,
        image_urls=images,
        categories=category_service.categories_map(db),
        db=db,
    )


@router.post("", response_model=ItemOut)
async def create_item(
    body: ItemCreate,
    token: str,
    db: Session = Depends(get_db),
):
    user = get_current_user(token, db)
    org, _ = org_service.require_active_org(db, user)
    await ai_moderation.assert_item_allowed(
        db,
        name=body.name,
        category=body.category,
        description=body.description or "",
        condition=body.condition or "",
        image_urls=body.images or [],
    )
    value = await _estimate_for_item(
        db, body.name, body.category, body.description, body.condition, body.images or [],
    )
    ai_coins = value["suggested_coins"]
    user_coins = body.value_coins if body.value_coins is not None else ai_coins
    item = Item(
        owner_id=user.id,
        org_id=org.id,
        name=body.name,
        category=body.category,
        description=body.description,
        images=",".join(body.images),
        condition=body.condition,
        value_coins=user_coins,
        ai_value_coins=ai_coins,
        want_tags=",".join(body.want_tags),
    )
    db.add(item)
    db.flush()
    coin_service.grant_list_item_reward(db, user, item.id)
    db.commit()
    db.refresh(item)
    return item.to_dict()


# ---- 分类（数据库配置，公开；必须声明在 /{item_id} 之前，避免被遮蔽）----
@router.get("/categories")
def categories_list(db: Session = Depends(get_db)):
    cats = category_service.list_active(db)
    return {"categories": [c.to_dict() for c in cats]}


@router.get("", response_model=list[ItemOut])
def list_items(
    token: str,
    category: str = "",
    keyword: str = Query("", max_length=32),
    owner: str = "",
    status: str = "on_shelf",
    db: Session = Depends(get_db),
):
    user = get_current_user(token, db)
    org, _ = org_service.require_active_org(db, user)
    q = db.query(Item).filter(Item.org_id == org.id)
    if status != "all":
        q = q.filter(Item.status == status)
    if category:
        q = q.filter(Item.category == category)
    if owner:
        q = q.filter(Item.owner.has(nickname=owner))
    if keyword:
        q = q.filter(Item.name.like(f"%{keyword}%"))
    items = q.order_by(Item.created_at.desc()).limit(100).all()
    return [i.to_dict() for i in items]


@router.get("/mine", response_model=list[ItemOut])
def my_items(token: str, db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    q = db.query(Item).filter(Item.owner_id == user.id)
    if user.active_org_id:
        q = q.filter(Item.org_id == user.active_org_id)
    items = q.order_by(Item.created_at.desc()).all()
    return [i.to_dict() for i in items]


# 注意：静态路由须声明在 /{item_id} 之前，否则被其捕获
@router.get("/report-reasons")
def report_reasons():
    return {"reasons": REPORT_REASONS}


@router.get("/ai-settings")
def public_ai_settings(db: Session = Depends(get_db)):
    """小程序可读：是否开启 AI 估值 / 合规检测。"""
    return ai_moderation.get_ai_settings(db)


@router.post("/ai-pricing", response_model=AIPricingOut)
async def ai_pricing(
    body: AIPricingIn,
    request: Request,
    token: str = "",
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    user = get_current_user(resolve_token(token, authorization), db)
    ip = rate_limit.client_ip(request)
    rate_limit.check("ai-pricing", f"user:{user.id}", max_hits=10, window_sec=60)
    rate_limit.check("ai-pricing", f"ip:{ip}", max_hits=30, window_sec=60)
    return await _estimate_for_item(
        db, body.name, body.category, body.description, body.condition, body.image_urls,
    )


@router.post("/ai-moderate")
async def ai_moderate(body: AIPricingIn, token: str = "", db: Session = Depends(get_db)):
    """上架前可预检；关闭开关时直接 allowed=true。需登录。"""
    get_current_user(token, db)
    return await ai_moderation.moderate_item(
        db,
        name=body.name,
        category=body.category,
        description=body.description or "",
        condition=body.condition or "",
        image_urls=body.image_urls or [],
    )


@router.get("/{item_id}", response_model=ItemOut)
def get_item(item_id: int, token: str, db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(404, "物品不存在")
    if item.owner_id != user.id:
        org, _ = org_service.require_active_org(db, user)
        if item.org_id != org.id:
            raise HTTPException(403, "只能查看本组织的闲置")
    return item.to_dict()


@router.put("/{item_id}", response_model=ItemOut)
async def update_item(item_id: int, body: ItemUpdate, token: str, db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    item = db.get(Item, item_id)
    if not item or item.owner_id != user.id:
        raise HTTPException(404, "物品不存在")
    if item.status == "swapping":
        raise HTTPException(400, "交换中的物品暂不能编辑")

    if body.name is not None:
        item.name = body.name
    if body.category is not None:
        item.category = body.category
    if body.description is not None:
        item.description = body.description
    if body.images is not None:
        item.images = ",".join(body.images)
    if body.condition is not None:
        item.condition = body.condition
    if body.want_tags is not None:
        item.want_tags = ",".join(body.want_tags)
    if body.value_coins is not None:
        item.value_coins = body.value_coins
    if body.status is not None:
        if body.status not in ("on_shelf", "off_shelf"):
            raise HTTPException(400, "状态只能是 on_shelf / off_shelf")
        if item.status == "swapped":
            raise HTTPException(400, "已交换出去的物品不能改状态")
        item.status = body.status
    if body.condition is not None or body.name is not None or body.category is not None or body.description is not None or body.images is not None:
        await ai_moderation.assert_item_allowed(
            db,
            name=item.name,
            category=item.category,
            description=item.description or "",
            condition=item.condition or "",
            image_urls=[u for u in (item.images or "").split(",") if u],
        )
    if body.condition is not None or body.name is not None or body.category is not None:
        images = [u for u in (item.images or "").split(",") if u]
        value = await _estimate_for_item(
            db, item.name, item.category, item.description, item.condition, images,
        )
        item.ai_value_coins = value["suggested_coins"]
    db.commit()
    db.refresh(item)
    return item.to_dict()


@router.delete("/{item_id}", response_model=Msg)
def delete_item(item_id: int, token: str, db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    item = db.get(Item, item_id)
    if not item or item.owner_id != user.id:
        raise HTTPException(404, "物品不存在")
    if item.status == "swapping":
        raise HTTPException(400, "交换中的物品不能删除，请先取消交换")
    db.delete(item)
    db.commit()
    return Msg(message="已下架删除")


# ---- 举报（家长/游客入口） --------------------------------------------------
@router.post("/{item_id}/report", response_model=Msg)
def report_item(item_id: int, body: ReportCreate, token: str, db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(404, "物品不存在")
    if body.reason not in REPORT_REASONS:
        raise HTTPException(400, "无效的举报理由")

    exists = (
        db.query(Report)
        .filter(Report.item_id == item_id, Report.reporter_id == user.id)
        .first()
    )
    if exists:
        raise HTTPException(400, "你已举报过该物品，管理员正在处理")

    report = Report(
        item_id=item_id,
        reporter_id=user.id,
        reason=body.reason,
        reporter_note=body.note,
        status="pending",
    )
    db.add(report)
    item.reported = (item.reported or 0) + 1
    item.flagged = True
    db.commit()
    return Msg(message="举报成功，已提交管理员审核")
