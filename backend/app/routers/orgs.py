"""组织路由：申请创建、邀请加入、切换、组织管理员（小程序内）。"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import get_db
from ..models import Item, Organization, OrgMembership, User
from ..routers.auth import get_current_user
from ..schemas import Msg
from ..services import org_service

router = APIRouter(prefix="/orgs", tags=["orgs"])


class OrgApplyIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=64)
    org_type: str = Field("school", max_length=16)
    description: str = Field("", max_length=500)


class OrgJoinIn(BaseModel):
    invite_code: str = Field(..., min_length=4, max_length=16)


class OrgSwitchIn(BaseModel):
    org_id: int


class MemberHandleIn(BaseModel):
    action: str = Field(..., max_length=16)  # approve / reject
    note: str = Field("", max_length=200)


class OrgRemoveItemIn(BaseModel):
    reason: str = Field("组织管理员下架", max_length=255)


# ---- 用户侧 ------------------------------------------------------------

@router.post("/apply")
def apply_org(body: OrgApplyIn, token: str, db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    if body.org_type not in org_service.ORG_TYPES:
        raise HTTPException(400, "组织类型只能是 school / community / other")
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "组织名称不能为空")

    pending = (
        db.query(Organization)
        .filter(Organization.creator_id == user.id, Organization.status == "pending")
        .first()
    )
    if pending:
        raise HTTPException(400, "你已有待审核的组织申请，请等待平台审核")

    org = Organization(
        name=name,
        org_type=body.org_type,
        description=(body.description or "").strip(),
        status="pending",
        creator_id=user.id,
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org.to_dict()


@router.get("/mine")
def my_orgs(token: str, db: Session = Depends(get_db)):
    """我创建的 + 我加入的（含 pending）。"""
    user = get_current_user(token, db)
    created = (
        db.query(Organization)
        .filter(Organization.creator_id == user.id)
        .order_by(Organization.created_at.desc())
        .all()
    )
    memberships = (
        db.query(OrgMembership)
        .filter(OrgMembership.user_id == user.id, OrgMembership.status != "left")
        .order_by(OrgMembership.created_at.desc())
        .all()
    )
    return {
        "active_org_id": user.active_org_id or 0,
        "created": [o.to_dict(include_invite=(o.status == "approved" and o.creator_id == user.id)) for o in created],
        "memberships": [m.to_dict() for m in memberships],
    }


@router.get("/current")
def current_org(token: str, db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    if not user.active_org_id:
        return {"org": None, "membership": None}
    try:
        org, mem = org_service.require_active_org(db, user)
    except HTTPException:
        return {"org": None, "membership": None}
    return {
        "org": org.to_dict(include_invite=mem.is_org_admin),
        "membership": mem.to_dict(),
    }


@router.post("/switch")
def switch_org(body: OrgSwitchIn, token: str, db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    org = db.get(Organization, body.org_id)
    if not org or org.status != "approved":
        raise HTTPException(404, "组织不存在或未通过审核")
    mem = org_service.get_membership(db, org.id, user.id)
    if not mem or mem.status != "active":
        raise HTTPException(403, "你还不是该组织的正式成员")
    user.active_org_id = org.id
    db.commit()
    return {"ok": True, "active_org_id": org.id, "org": org.to_dict(include_invite=mem.is_org_admin)}


@router.post("/join")
def join_org(body: OrgJoinIn, token: str, db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    code = body.invite_code.strip().upper()
    org = db.query(Organization).filter(Organization.invite_code == code).first()
    if not org or org.status != "approved":
        raise HTTPException(404, "邀请码无效或组织不可用")

    mem = org_service.get_membership(db, org.id, user.id)
    if mem:
        if mem.status == "active":
            raise HTTPException(400, "你已是该组织成员")
        if mem.status == "pending":
            raise HTTPException(400, "加入申请已提交，请等待组织管理员审核")
        # rejected / left → 重新申请
        mem.status = "pending"
        mem.role = "member"
        mem.handle_note = ""
        mem.handled_by = 0
        mem.handled_at = None
    else:
        mem = OrgMembership(
            org_id=org.id,
            user_id=user.id,
            role="member",
            status="pending",
        )
        db.add(mem)
    db.commit()
    db.refresh(mem)
    return {"ok": True, "message": "已提交加入申请，请等待组织管理员审核", "membership": mem.to_dict()}


# ---- 组织管理员（小程序内，非超管后台） --------------------------------

@router.get("/{org_id}/members")
def list_members(org_id: int, status: str = "pending", token: str = "", db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    org_service.require_org_admin(db, user, org_id)
    q = db.query(OrgMembership).filter(OrgMembership.org_id == org_id)
    if status != "all":
        q = q.filter(OrgMembership.status == status)
    rows = q.order_by(OrgMembership.created_at.desc()).limit(200).all()
    return [m.to_dict() for m in rows]


@router.post("/{org_id}/members/{membership_id}")
def handle_member(
    org_id: int,
    membership_id: int,
    body: MemberHandleIn,
    token: str = "",
    db: Session = Depends(get_db),
):
    user = get_current_user(token, db)
    org_service.require_org_admin(db, user, org_id)
    mem = db.get(OrgMembership, membership_id)
    if not mem or mem.org_id != org_id:
        raise HTTPException(404, "成员申请不存在")
    if mem.status != "pending":
        raise HTTPException(400, "该申请已处理")
    if mem.role == "owner":
        raise HTTPException(400, "不能变更创建者状态")

    if body.action == "approve":
        mem.status = "active"
        mem.handle_note = body.note or "通过"
        # 若用户尚无当前组织，自动切到本组织
        member_user = db.get(User, mem.user_id)
        if member_user and not member_user.active_org_id:
            member_user.active_org_id = org_id
    elif body.action == "reject":
        mem.status = "rejected"
        mem.handle_note = body.note or "未通过"
    else:
        raise HTTPException(400, "action 只能是 approve / reject")

    mem.handled_by = user.id
    mem.handled_at = datetime.utcnow()
    db.commit()
    db.refresh(mem)
    return mem.to_dict()


@router.post("/{org_id}/invite/refresh")
def refresh_invite(org_id: int, token: str = "", db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    org, _ = org_service.require_org_admin(db, user, org_id)
    org.invite_code = org_service.generate_invite_code(db)
    db.commit()
    return {"invite_code": org.invite_code}


@router.get("/{org_id}/items")
def org_items(
    org_id: int,
    status: str = "on_shelf",
    token: str = "",
    db: Session = Depends(get_db),
):
    """组织管理员查看本组织闲置。"""
    user = get_current_user(token, db)
    org_service.require_org_admin(db, user, org_id)
    q = db.query(Item).filter(Item.org_id == org_id)
    if status != "all":
        q = q.filter(Item.status == status)
    items = q.order_by(Item.created_at.desc()).limit(100).all()
    return [i.to_dict() for i in items]


@router.post("/{org_id}/items/{item_id}/remove")
def org_remove_item(
    org_id: int,
    item_id: int,
    body: OrgRemoveItemIn,
    token: str = "",
    db: Session = Depends(get_db),
):
    user = get_current_user(token, db)
    org_service.require_org_admin(db, user, org_id)
    item = db.get(Item, item_id)
    if not item or item.org_id != org_id:
        raise HTTPException(404, "物品不存在或不属于本组织")
    if item.status == "swapped":
        raise HTTPException(400, "已换出的物品不可下架")
    item.status = "removed"
    item.removed_reason = body.reason or "组织管理员下架"
    item.removed_by = user.id
    item.flagged = True
    db.commit()
    return Msg(message="已下架")
