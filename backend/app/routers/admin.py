"""内容治理：管理员后台 —— 查看被举报物品、下架 / 驳回。

合规要点：
- 仅 role=admin 的用户可访问（get_current_admin 校验）。
- 物品被举报后仍可见但下沉展示（举报即公示），由管理员审理后：下架 / 保留 / 驳回。
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import get_db
from ..models import AdminUser, Category, Item, LlmProvider, Organization, Report, User
from ..routers.auth import get_current_user
from ..schemas import CategoryCreate, CategoryUpdate, LlmProviderCreate, LlmProviderUpdate, Msg, OrgReviewIn, ReportHandle
from ..services import admin_auth as admin_auth_svc
from ..services import llm_service
from ..services import org_service

router = APIRouter(prefix="/admin", tags=["admin"])


def get_current_admin(token: str, db: Session) -> User:
    """只有 admin 能调用治理接口。支持两类令牌：
    - 小程序管理员：openid 账号（role=admin）
    - 独立后台管理员：admin-web- 开头的令牌（admin_users 表）
    """
    if token.startswith(admin_auth_svc.ADMIN_WEB_TOKEN_PREFIX):
        admin_id = admin_auth_svc.parse_admin_token(token)
        admin = db.get(AdminUser, admin_id)
        if not admin or not admin.is_active:
            raise HTTPException(401, "管理员不存在或已停用")
        return admin  # 类型上可能是 AdminUser
    user = get_current_user(token, db)
    if user.role != "admin":
        raise HTTPException(403, "需要管理员权限")
    return user


@router.get("/me")
def admin_me(token: str = "", db: Session = Depends(get_db)):
    user = get_current_admin(token, db)
    return {"ok": True, "is_admin": True, "nickname": user.nickname}


@router.get("/reports")
def list_reports(status: str = "pending", token: str = "", db: Session = Depends(get_db)):
    get_current_admin(token, db)
    q = db.query(Report)
    if status != "all":
        q = q.filter(Report.status == status)
    reports = (
        q.order_by(Report.created_at.desc())
        .limit(100)
        .all()
    )
    return [r.to_dict() for r in reports]


@router.get("/items")
def list_flagged_items(token: str = "", db: Session = Depends(get_db)):
    """被举报或已下架的物品（供管理员快速排查）。"""
    get_current_admin(token, db)
    items = (
        db.query(Item)
        .filter(Item.reported > 0)
        .order_by(Item.reported.desc(), Item.created_at.desc())
        .limit(100)
        .all()
    )
    return [i.to_dict() for i in items]


@router.post("/reports/{report_id}")
def handle_report(
    report_id: int,
    body: ReportHandle,
    token: str = "",
    db: Session = Depends(get_db),
):
    """处理举报：remove(下架) / reject(驳回) / keep(记录但保留)。"""
    admin = get_current_admin(token, db)
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(404, "举报不存在")
    if report.status != "pending":
        raise HTTPException(400, "该举报已处理")

    item = db.get(Item, report.item_id)

    action = body.action
    if action == "remove":
        # 下架：设置为 removed 状态，跳出不展示
        if item:
            item.status = "removed"
            item.removed_reason = body.reason
            item.removed_by = admin.id
            item.flagged = True
        report.status = "resolved"
        report.handle_note = body.reason
    elif action in ("reject", "keep"):
        # 驳回：认定无违规，物品保持原状（物主可自行上下架）
        report.status = "rejected"
        report.handle_note = body.reason
        # 举报已处理，取消置顶标记（管理员判为无违规）
        if item:
            item.flagged = False
    else:
        raise HTTPException(400, "action 只能是 remove / reject / keep")

    report.handled_by = admin.id
    report.handled_at = datetime.utcnow()
    db.commit()
    return report.to_dict()


@router.post("/item/{item_id}/remove")
def admin_remove_item(item_id: int, token: str = "", db: Session = Depends(get_db)):
    """管理员直接下架某物品（无需先举报）。"""
    admin = get_current_admin(token, db)
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(404, "物品不存在")
    if item.status == "swapped":
        raise HTTPException(400, "已换出的物品不可下架")
    item.status = "removed"
    item.removed_reason = "管理员人工下架"
    item.removed_by = admin.id
    item.flagged = True
    db.commit()
    return {"ok": True, "message": "已下架"}


# ---- 物品管理（独立后台：浏览全部 + 上架/下架/恢复） -----------------------
@router.get("/items/all")
def admin_list_all_items(
    status: str = "all",
    keyword: str = "",
    page: int = 1,
    page_size: int = 20,
    token: str = "",
    db: Session = Depends(get_db),
):
    """后台浏览全部物品（含已下架/已交换），可分页、可按关键词/状态筛选。"""
    get_current_admin(token, db)
    page = max(1, page)
    page_size = min(50, max(1, page_size))
    q = db.query(Item)
    if status != "all":
        q = q.filter(Item.status == status)
    if keyword:
        q = q.filter(Item.name.like(f"%{keyword}%"))
    total = q.count()
    items = (
        q.order_by(Item.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"total": total, "items": [i.to_dict() for i in items]}


@router.post("/item/{item_id}/status")
def admin_set_item_status(
    item_id: int,
    status: str,
    token: str = "",
    db: Session = Depends(get_db),
):
    """后台把物品切换到 on_shelf / off_shelf / removed（swapped 不可改）。"""
    get_current_admin(token, db)
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(404, "物品不存在")
    if item.status == "swapped":
        raise HTTPException(400, "已换出的物品不可改状态")
    if status not in ("on_shelf", "off_shelf", "removed"):
        raise HTTPException(400, "状态只能是 on_shelf / off_shelf / removed")
    item.status = status
    if status == "removed":
        item.removed_reason = item.removed_reason or "管理员下架"
        item.flagged = True
    db.commit()
    return {"ok": True, "message": "已更新状态", "status": item.status}


# ---- 孩子/积分管理（独立后台）----------------------------------------------
@router.get("/users")
def admin_list_users(
    keyword: str = "",
    page: int = 1,
    page_size: int = 20,
    token: str = "",
    db: Session = Depends(get_db),
):
    """孩子列表与咸鱼币结余（可按昵称/班级搜索）。"""
    get_current_admin(token, db)
    page = max(1, page)
    page_size = min(50, max(1, page_size))
    q = db.query(User)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter((User.nickname.like(like)) | (User.grade_class.like(like)))
    total = q.count()
    users = (
        q.order_by(User.coin_balance.desc(), User.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"total": total, "users": [u.to_dict() for u in users]}


@router.post("/user/{user_id}/toggle")
def admin_toggle_user(user_id: int, token: str = "", db: Session = Depends(get_db)):
    """停用/启用一个孩子账号（停用后无法登录、其上架物品不予展示）。"""
    get_current_admin(token, db)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    user.is_active = not user.is_active
    db.commit()
    return {"ok": True, "is_active": user.is_active, "nickname": user.nickname}


# ---- 分类管理（仅管理员，玩家只读）--------------------------------
@router.get("/categories")
def admin_list_categories(token: str = "", db: Session = Depends(get_db)):
    get_current_admin(token, db)
    cats = db.query(Category).order_by(Category.sort_order, Category.id).all()
    return [c.to_dict() for c in cats]


@router.post("/categories")
def admin_create_category(body: CategoryCreate, token: str = "", db: Session = Depends(get_db)):
    get_current_admin(token, db)
    if db.query(Category).filter(Category.name == body.name).first():
        raise HTTPException(400, "分类已存在")
    cat = Category(
        name=body.name.strip(),
        value_base=body.value_base,
        note=body.note or "",
        sort_order=body.sort_order,
        is_active=body.is_active,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat.to_dict()


@router.put("/categories/{category_id}")
def admin_update_category(
    category_id: int,
    body: CategoryUpdate,
    token: str = "",
    db: Session = Depends(get_db),
):
    get_current_admin(token, db)
    cat = db.get(Category, category_id)
    if not cat:
        raise HTTPException(404, "分类不存在")
    change = body.model_dump(exclude_unset=True)
    if "name" in change and change["name"] != cat.name:
        if db.query(Category).filter(Category.name == change["name"], Category.id != category_id).first():
            raise HTTPException(400, "同名分类已存在")
        cat.name = change["name"].strip()
    if "value_base" in change:
        cat.value_base = change["value_base"]
    if "note" in change:
        cat.note = change["note"] or ""
    if "sort_order" in change:
        cat.sort_order = change["sort_order"]
    if "is_active" in change:
        cat.is_active = change["is_active"]
    db.commit()
    db.refresh(cat)
    return cat.to_dict()


@router.delete("/categories/{category_id}")
def admin_delete_category(category_id: int, token: str = "", db: Session = Depends(get_db)):
    get_current_admin(token, db)
    cat = db.get(Category, category_id)
    if not cat:
        raise HTTPException(404, "分类不存在")
    used = db.query(Item).filter(Item.category == cat.name).count()
    if used:
        raise HTTPException(
            400, f"已有 {used} 件闲置使用该分类，不能删除；可改为停用"
        )
    db.delete(cat)
    db.commit()
    return {"ok": True, "message": "已删除"}

# ---- 组织创建审核（仅平台超管；组织日常管理在小程序） --------------------
@router.get("/orgs")
def admin_list_orgs(status: str = "pending", token: str = "", db: Session = Depends(get_db)):
    get_current_admin(token, db)
    q = db.query(Organization)
    if status != "all":
        q = q.filter(Organization.status == status)
    orgs = q.order_by(Organization.created_at.desc()).limit(100).all()
    return [o.to_dict(include_invite=(o.status == "approved")) for o in orgs]


@router.post("/orgs/{org_id}/review")
def admin_review_org(
    org_id: int,
    body: OrgReviewIn,
    token: str = "",
    db: Session = Depends(get_db),
):
    admin = get_current_admin(token, db)
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "组织不存在")
    if org.status != "pending":
        raise HTTPException(400, "该申请已处理")

    if body.action == "approve":
        org_service.approve_organization(db, org, reviewer_id=admin.id)
    elif body.action == "reject":
        org_service.reject_organization(db, org, reviewer_id=admin.id, reason=body.reason)
    else:
        raise HTTPException(400, "action 只能是 approve / reject")

    db.commit()
    db.refresh(org)
    return org.to_dict(include_invite=(org.status == "approved"))


# ---- 大模型 API 配置（多 Key 故障切换） ---------------------------------
@router.get("/llm/vendors")
def admin_llm_vendors(token: str = "", db: Session = Depends(get_db)):
    get_current_admin(token, db)
    return [
        {"vendor": k, **v}
        for k, v in llm_service.VENDOR_PRESETS.items()
    ]


@router.get("/llm/providers")
def admin_list_llm(token: str = "", db: Session = Depends(get_db)):
    get_current_admin(token, db)
    return [p.to_dict() for p in llm_service.list_providers(db)]


@router.post("/llm/providers")
def admin_create_llm(body: LlmProviderCreate, token: str = "", db: Session = Depends(get_db)):
    get_current_admin(token, db)
    vendor = (body.vendor or "custom").strip().lower()
    if vendor not in llm_service.KNOWN_VENDORS:
        raise HTTPException(400, f"未知厂商，可选：{', '.join(llm_service.KNOWN_VENDORS)}")
    row = LlmProvider(
        name=body.name.strip(),
        vendor=vendor,
        base_url=body.base_url.strip().rstrip("/"),
        api_key=body.api_key.strip(),
        model=body.model.strip(),
        is_active=body.is_active,
        sort_order=body.sort_order,
        timeout_sec=body.timeout_sec,
        note=(body.note or "").strip(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row.to_dict()


@router.put("/llm/providers/{provider_id}")
def admin_update_llm(
    provider_id: int,
    body: LlmProviderUpdate,
    token: str = "",
    db: Session = Depends(get_db),
):
    get_current_admin(token, db)
    row = db.get(LlmProvider, provider_id)
    if not row:
        raise HTTPException(404, "配置不存在")
    data = body.model_dump(exclude_unset=True)
    if "vendor" in data and data["vendor"]:
        vendor = data["vendor"].strip().lower()
        if vendor not in llm_service.KNOWN_VENDORS:
            raise HTTPException(400, f"未知厂商，可选：{', '.join(llm_service.KNOWN_VENDORS)}")
        row.vendor = vendor
    if "name" in data and data["name"] is not None:
        row.name = data["name"].strip()
    if "base_url" in data and data["base_url"] is not None:
        row.base_url = data["base_url"].strip().rstrip("/")
    if "api_key" in data and data["api_key"]:
        # 空字符串 / 仅占位不改；传新 key 才更新
        row.api_key = data["api_key"].strip()
    if "model" in data and data["model"] is not None:
        row.model = data["model"].strip()
    if "is_active" in data and data["is_active"] is not None:
        row.is_active = data["is_active"]
    if "sort_order" in data and data["sort_order"] is not None:
        row.sort_order = data["sort_order"]
    if "timeout_sec" in data and data["timeout_sec"] is not None:
        row.timeout_sec = data["timeout_sec"]
    if "note" in data:
        row.note = (data["note"] or "").strip()
    db.commit()
    db.refresh(row)
    return row.to_dict()


@router.delete("/llm/providers/{provider_id}")
def admin_delete_llm(provider_id: int, token: str = "", db: Session = Depends(get_db)):
    get_current_admin(token, db)
    row = db.get(LlmProvider, provider_id)
    if not row:
        raise HTTPException(404, "配置不存在")
    db.delete(row)
    db.commit()
    return {"ok": True, "message": "已删除"}


@router.post("/llm/providers/{provider_id}/test")
def admin_test_llm(provider_id: int, token: str = "", db: Session = Depends(get_db)):
    """探测连通性（文本请求，不烧视觉额度）。"""
    get_current_admin(token, db)
    row = db.get(LlmProvider, provider_id)
    if not row:
        raise HTTPException(404, "配置不存在")
    if not row.api_key:
        raise HTTPException(400, "未配置 API Key")
    endpoint = {
        "id": row.id,
        "name": row.name,
        "base_url": row.base_url,
        "api_key": row.api_key,
        "model": row.model,
        "timeout_sec": row.timeout_sec or 30,
    }
    try:
        from ..services.ai_pricing import probe_endpoint

        result = probe_endpoint(endpoint)
        llm_service.mark_success(db, row.id)
        return {"ok": True, "message": "连通正常", **result}
    except Exception as e:  # noqa: BLE001
        llm_service.mark_failure(db, row.id, str(e))
        raise HTTPException(400, f"连通失败：{e}")
