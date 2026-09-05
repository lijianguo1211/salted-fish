"""组织服务：邀请码、成员身份校验、当前组织上下文。"""
import secrets
import string
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Organization, OrgMembership, User

ORG_TYPES = ("school", "community", "other")
ORG_TYPE_LABEL = {"school": "学校", "community": "小区", "other": "其他"}


def generate_invite_code(db: Session, length: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(20):
        code = "".join(secrets.choice(alphabet) for _ in range(length))
        if not db.query(Organization).filter(Organization.invite_code == code).first():
            return code
    raise HTTPException(500, "邀请码生成失败，请重试")


def get_membership(db: Session, org_id: int, user_id: int) -> OrgMembership | None:
    return (
        db.query(OrgMembership)
        .filter(OrgMembership.org_id == org_id, OrgMembership.user_id == user_id)
        .first()
    )


def require_active_org(db: Session, user: User) -> tuple[Organization, OrgMembership]:
    """当前选中组织必须存在，且用户是该组织的 active 成员。"""
    if not user.active_org_id:
        raise HTTPException(400, "请先选择一个组织")
    org = db.get(Organization, user.active_org_id)
    if not org or org.status != "approved":
        raise HTTPException(400, "当前组织不可用，请重新选择")
    mem = get_membership(db, org.id, user.id)
    if not mem or mem.status != "active":
        raise HTTPException(403, "你还不是该组织的正式成员")
    return org, mem


def require_org_admin(db: Session, user: User, org_id: int) -> tuple[Organization, OrgMembership]:
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "组织不存在")
    if org.status != "approved":
        raise HTTPException(400, "组织尚未通过平台审核")
    mem = get_membership(db, org_id, user.id)
    if not mem or not mem.is_org_admin:
        raise HTTPException(403, "需要组织管理员权限")
    return org, mem


def approve_organization(db: Session, org: Organization, reviewer_id: int) -> Organization:
    """平台审核通过：生成邀请码，创建者成为 owner。"""
    org.status = "approved"
    org.reject_reason = ""
    org.reviewed_by = reviewer_id
    org.reviewed_at = datetime.utcnow()
    if not org.invite_code:
        org.invite_code = generate_invite_code(db)

    mem = get_membership(db, org.id, org.creator_id)
    if not mem:
        mem = OrgMembership(
            org_id=org.id,
            user_id=org.creator_id,
            role="owner",
            status="active",
            handled_by=reviewer_id,
            handled_at=datetime.utcnow(),
            handle_note="创建者自动成为组织管理员",
        )
        db.add(mem)
    else:
        mem.role = "owner"
        mem.status = "active"
        mem.handled_by = reviewer_id
        mem.handled_at = datetime.utcnow()

    creator = db.get(User, org.creator_id)
    if creator and not creator.active_org_id:
        creator.active_org_id = org.id
    db.flush()
    return org


def reject_organization(db: Session, org: Organization, reviewer_id: int, reason: str) -> Organization:
    org.status = "rejected"
    org.reject_reason = reason or "未通过审核"
    org.reviewed_by = reviewer_id
    org.reviewed_at = datetime.utcnow()
    db.flush()
    return org
