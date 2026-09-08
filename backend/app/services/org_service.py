"""组织服务：邀请码、成员身份校验、当前组织上下文。"""
import secrets
import string
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Organization, OrgMembership, User

ORG_TYPES = ("school", "community", "other")
ORG_TYPE_LABEL = {"school": "学校", "community": "小区", "other": "其他"}
DEFAULT_MAX_ORGS_PER_CREATOR = 3
SETTING_MAX_ORGS = "max_orgs_per_creator"


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


def get_setting(db: Session, key: str, default: str = "") -> str:
    from ..models import AppSetting

    row = db.get(AppSetting, key)
    if not row or row.value is None or row.value == "":
        return default
    return row.value


def set_setting(db: Session, key: str, value: str) -> str:
    from ..models import AppSetting

    row = db.get(AppSetting, key)
    if not row:
        row = AppSetting(key=key, value=str(value))
        db.add(row)
    else:
        row.value = str(value)
    db.flush()
    return row.value


def default_max_orgs(db: Session) -> int:
    raw = get_setting(db, SETTING_MAX_ORGS, str(DEFAULT_MAX_ORGS_PER_CREATOR))
    try:
        n = int(raw)
    except (TypeError, ValueError):
        n = DEFAULT_MAX_ORGS_PER_CREATOR
    return max(1, min(n, 50))


def user_create_limit(db: Session, user: User) -> int:
    if user.org_create_limit is not None and user.org_create_limit > 0:
        return int(user.org_create_limit)
    return default_max_orgs(db)


def count_created_orgs(db: Session, user_id: int) -> int:
    """占用名额：待审 + 已通过（驳回不占）。"""
    return (
        db.query(Organization)
        .filter(
            Organization.creator_id == user_id,
            Organization.status.in_(("pending", "approved")),
        )
        .count()
    )


def create_quota_info(db: Session, user: User) -> dict:
    limit = user_create_limit(db, user)
    used = count_created_orgs(db, user.id)
    remaining = max(0, limit - used)
    return {
        "default_limit": default_max_orgs(db),
        "limit": limit,
        "used": used,
        "remaining": remaining,
        "can_create": remaining > 0,
        "personal_limit": user.org_create_limit,
    }


def assert_can_create_org(db: Session, user: User) -> dict:
    info = create_quota_info(db, user)
    if not info["can_create"]:
        raise HTTPException(
            400,
            f"每人默认可创建 {info['limit']} 个组织，你已用满。"
            "如需更多，请提交超额申请并上传证明（如教师资格证）。",
        )
    return info
