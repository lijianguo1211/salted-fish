"""组织路由：申请创建、邀请加入、切换、组织管理员（小程序内）。"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import get_db
from ..models import Item, Organization, OrgMembership, OrgQuotaApplication, User
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


class OrgSettingsIn(BaseModel):
    invite_enabled: bool | None = None
    join_need_review: bool | None = None


class OrgQuotaApplyIn(BaseModel):
    reason: str = Field(..., min_length=20, max_length=1000)
    proof_urls: list[str] = Field(default_factory=list)
    requested_limit: int = Field(..., ge=2, le=50)


# ---- 用户侧 ------------------------------------------------------------

@router.get("/create-quota")
def get_create_quota(token: str, db: Session = Depends(get_db)):
    """查询当前用户可创建组织额度。"""
    user = get_current_user(token, db)
    return org_service.create_quota_info(db, user)


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

    org_service.assert_can_create_org(db, user)

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


@router.post("/quota-applications")
def apply_org_quota(body: OrgQuotaApplyIn, token: str, db: Session = Depends(get_db)):
    """超额创建额度申请：说明原因 + 附件证明。"""
    user = get_current_user(token, db)
    info = org_service.create_quota_info(db, user)
    if body.requested_limit <= info["limit"]:
        raise HTTPException(400, f"申请上限须大于当前额度 {info['limit']}")

    reason = body.reason.strip()
    if len(reason) < 20:
        raise HTTPException(400, "请详细说明为什么需要创建更多组织（至少 20 字）")

    proofs = [u.strip() for u in (body.proof_urls or []) if u and u.strip()]
    if not proofs:
        raise HTTPException(400, "请上传至少一张证明材料（如教师资格证）")
    if len(proofs) > 5:
        raise HTTPException(400, "证明材料最多 5 张")
    for u in proofs:
        if not u.startswith("/uploads/"):
            raise HTTPException(400, "证明材料须先上传到本平台")

    pending = (
        db.query(OrgQuotaApplication)
        .filter(OrgQuotaApplication.user_id == user.id, OrgQuotaApplication.status == "pending")
        .first()
    )
    if pending:
        raise HTTPException(400, "你已有待审核的超额申请，请等待平台处理")

    row = OrgQuotaApplication(
        user_id=user.id,
        reason=reason,
        proof_urls=",".join(proofs),
        requested_limit=body.requested_limit,
        status="pending",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row.to_dict()


@router.get("/quota-applications/mine")
def my_quota_applications(token: str, db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    rows = (
        db.query(OrgQuotaApplication)
        .filter(OrgQuotaApplication.user_id == user.id)
        .order_by(OrgQuotaApplication.created_at.desc())
        .limit(20)
        .all()
    )
    return [r.to_dict() for r in rows]


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
        "org": org.to_dict(include_invite=True),
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
    return {"ok": True, "active_org_id": org.id, "org": org.to_dict(include_invite=True)}


@router.get("/{org_id}/invite")
def get_invite(org_id: int, token: str = "", db: Session = Depends(get_db)):
    """正式成员可查看邀请码并分享；刷新/失效/开关仅组织管理员。"""
    user = get_current_user(token, db)
    org = db.get(Organization, org_id)
    if not org or org.status != "approved":
        raise HTTPException(404, "组织不存在或未通过审核")
    mem = org_service.get_membership(db, org_id, user.id)
    if not mem or mem.status != "active":
        raise HTTPException(403, "只有正式成员可以邀请他人")

    invite_enabled = bool(org.invite_enabled if org.invite_enabled is not None else True)
    join_need_review = bool(org.join_need_review if org.join_need_review is not None else True)
    code = org.invite_code or ""
    show_code = invite_enabled and bool(code)
    share_text = ""
    if show_code:
        if join_need_review:
            share_text = (
                f"邀请你加入咸鱼小市场「{org.name}」！"
                f"点开分享卡片即可申请加入（邀请码 {code}）。"
            )
        else:
            share_text = (
                f"邀请你加入咸鱼小市场「{org.name}」！"
                f"点开分享卡片即可进入组织（邀请码 {code}）。"
            )
    return {
        "org_id": org.id,
        "org_name": org.name,
        "invite_code": code if show_code else "",
        "invite_enabled": invite_enabled,
        "join_need_review": join_need_review,
        "share_text": share_text,
        "can_manage": mem.is_org_admin,
        "can_refresh": mem.is_org_admin,
    }


@router.post("/join")
def join_org(body: OrgJoinIn, token: str, db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    code = body.invite_code.strip().upper()
    org = db.query(Organization).filter(Organization.invite_code == code).first()
    if not org or org.status != "approved":
        raise HTTPException(404, "邀请码无效或已失效")
    if not (org.invite_enabled if org.invite_enabled is not None else True):
        raise HTTPException(400, "该组织已关闭邀请，暂不可加入")

    need_review = bool(org.join_need_review if org.join_need_review is not None else True)
    new_status = "pending" if need_review else "active"

    mem = org_service.get_membership(db, org.id, user.id)
    if mem:
        if mem.status == "active":
            raise HTTPException(400, "你已是该组织成员")
        if mem.status == "pending":
            raise HTTPException(400, "加入申请已提交，请等待组织管理员审核")
        # rejected / left → 重新申请
        mem.status = new_status
        mem.role = "member"
        mem.handle_note = "" if need_review else "免审直接加入"
        mem.handled_by = 0 if need_review else user.id
        mem.handled_at = None if need_review else datetime.utcnow()
    else:
        mem = OrgMembership(
            org_id=org.id,
            user_id=user.id,
            role="member",
            status=new_status,
            handle_note="" if need_review else "免审直接加入",
            handled_by=0 if need_review else user.id,
            handled_at=None if need_review else datetime.utcnow(),
        )
        db.add(mem)

    if new_status == "active" and not user.active_org_id:
        user.active_org_id = org.id

    db.commit()
    db.refresh(mem)
    msg = (
        "已提交加入申请，请等待组织管理员审核"
        if need_review
        else "已加入组织"
    )
    return {"ok": True, "message": msg, "membership": mem.to_dict()}


# ---- 组织管理员（小程序内，非超管后台） --------------------------------

@router.put("/{org_id}/settings")
def update_org_settings(
    org_id: int,
    body: OrgSettingsIn,
    token: str = "",
    db: Session = Depends(get_db),
):
    """组织管理员：开关邀请、是否开启加入审核。"""
    user = get_current_user(token, db)
    org, _ = org_service.require_org_admin(db, user, org_id)
    if body.invite_enabled is not None:
        org.invite_enabled = body.invite_enabled
        if body.invite_enabled and not org.invite_code:
            org.invite_code = org_service.generate_invite_code(db)
    if body.join_need_review is not None:
        org.join_need_review = body.join_need_review
    db.commit()
    db.refresh(org)
    return org.to_dict(include_invite=True)


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
    """换发新邀请码（旧码立即失效），并开启邀请。"""
    user = get_current_user(token, db)
    org, _ = org_service.require_org_admin(db, user, org_id)
    org.invite_code = org_service.generate_invite_code(db)
    org.invite_enabled = True
    db.commit()
    return {
        "invite_code": org.invite_code,
        "invite_enabled": True,
        "message": "已换发新邀请码，旧码已失效",
    }


@router.post("/{org_id}/invite/invalidate")
def invalidate_invite(org_id: int, token: str = "", db: Session = Depends(get_db)):
    """使当前邀请码失效（清空），旧码不可再加入。"""
    user = get_current_user(token, db)
    org, _ = org_service.require_org_admin(db, user, org_id)
    org.invite_code = None
    db.commit()
    return {"ok": True, "invite_code": "", "message": "邀请码已失效"}


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
