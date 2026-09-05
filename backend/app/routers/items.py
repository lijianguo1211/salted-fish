"""物品路由：上架（AI 定价建议）、列表、我的、详情、下架、举报。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..config import REPORT_REASONS, get_db
from ..models import Item, Report
from ..schemas import AIPricingIn, AIPricingOut, ItemCreate, ItemOut, ItemUpdate, Msg, ReportCreate
from ..routers.auth import get_current_user
from ..services import coin_service
from ..services.ai_pricing import estimate_value
from ..services import category_service
from ..services import org_service

router = APIRouter(prefix="/items", tags=["items"])


@router.post("", response_model=ItemOut)
def create_item(
    body: ItemCreate,
    token: str,
    db: Session = Depends(get_db),
):
    user = get_current_user(token, db)
    org, _ = org_service.require_active_org(db, user)
    value = estimate_value(
        body.name, body.category, body.description, body.condition,
        categories=category_service.categories_map(db),
    )
    suggested = body.value_coins if body.value_coins is not None else value["suggested_coins"]
    item = Item(
        owner_id=user.id,
        org_id=org.id,
        name=body.name,
        category=body.category,
        description=body.description,
        images=",".join(body.images),
        condition=body.condition,
        value_coins=suggested,
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
def update_item(item_id: int, body: ItemUpdate, token: str, db: Session = Depends(get_db)):
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
    if body.condition is not None or body.name is not None or body.category is not None:
        value = estimate_value(
            item.name, item.category, item.description, item.condition,
            categories=category_service.categories_map(db),
        )
        item.value_coins = value["suggested_coins"]
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


# ---- AI 定价（独立接口，供小程序"拍照识别后先估价"交互） --------------------
@router.post("/ai-pricing", response_model=AIPricingOut)
def ai_pricing(body: AIPricingIn, db: Session = Depends(get_db)):
    return estimate_value(
        body.name, body.category, body.description, body.condition,
        image_urls=body.image_urls,
        categories=category_service.categories_map(db),
    )
