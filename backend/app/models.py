"""数据模型：用户、物品、交换请求、咸鱼币流水、排行。

设计要点：
- User.parent_openid 与 User.openid 分离 —— 孩子的操作全部需要家长微信确认。
- Item.value_coins 是 AI 建议参考值（枚），不是价格；交换不等值时由差价档位弥补，
  实际上交换是纯以物换物，value_coins 只用于匹配排序与展示。
- Swap.both_confirm 完成时同步发币。
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from sqlalchemy.orm import relationship

from .config import Base, COIN_INITIAL_BALANCE


class TimestampMixin:
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    openid = Column(String(64), unique=True, index=True)         # 孩子登录凭证
    parent_openid = Column(String(64), index=True)                # 家长微信
    nickname = Column(String(32), nullable=False)                # 显示名（孩子昵称）
    role = Column(String(16), default="student")                 # student / parent / teacher / admin
    school = Column(String(64), default="")
    grade_class = Column(String(32), default="")                  # 例如 "三年级2班"
    coin_balance = Column(Integer, default=0)              # 咸鱼币余额（积分）
    avatar = Column(String(255), default="")
    is_active = Column(Boolean, default=True)
    # use_alter：与 Organization.creator_id 形成环，建表时延后加约束
    active_org_id = Column(
        Integer, ForeignKey("organizations.id", use_alter=True, name="fk_users_active_org"),
        nullable=True, index=True,
    )

    items = relationship("Item", back_populates="owner")
    active_org = relationship("Organization", foreign_keys=[active_org_id])

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def to_dict(self):
        return {
            "id": self.id,
            "nickname": self.nickname,
            "role": self.role,
            "is_admin": self.is_admin,
            "school": self.school,
            "grade_class": self.grade_class,
            "coin_balance": self.coin_balance,
            "avatar": self.avatar,
            "active_org_id": self.active_org_id or 0,
            "active_org_name": self.active_org.name if self.active_org else "",
        }


class AdminUser(TimestampMixin, Base):
    """独立后台的管理员账号（邮箱 + 密码登录，区别于小程序 openid 账号）。"""

    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(128), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(64), default="管理员")
    is_active = Column(Boolean, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "is_active": self.is_active,
        }


class Organization(TimestampMixin, Base):
    """组织（小区 / 学校等）：内容与成员的隔离边界。

    状态机：pending（待平台审核）→ approved / rejected
    审核通过后生成邀请码；仅邀请码/链接可加入，加入后待组织管理员审核。
    """

    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), nullable=False)
    org_type = Column(String(16), default="school")  # school / community / other
    description = Column(Text, default="")
    status = Column(String(16), default="pending", index=True)  # pending / approved / rejected
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    invite_code = Column(String(16), unique=True, nullable=True, index=True)
    reject_reason = Column(String(255), default="")
    reviewed_by = Column(Integer, default=0)  # 平台管理员 id（AdminUser 或 User）
    reviewed_at = Column(DateTime, nullable=True)

    creator = relationship("User", foreign_keys=[creator_id])
    memberships = relationship("OrgMembership", back_populates="org", lazy="dynamic")

    def to_dict(self, *, include_invite: bool = False):
        data = {
            "id": self.id,
            "name": self.name,
            "org_type": self.org_type,
            "description": self.description or "",
            "status": self.status,
            "creator_id": self.creator_id,
            "creator_name": self.creator.nickname if self.creator else "",
            "reject_reason": self.reject_reason or "",
            "reviewed_at": self.reviewed_at.strftime("%Y-%m-%d %H:%M") if self.reviewed_at else "",
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else "",
            "member_count": self.memberships.filter_by(status="active").count()
            if self.memberships is not None
            else 0,
        }
        if include_invite:
            data["invite_code"] = self.invite_code or ""
        return data


class OrgMembership(TimestampMixin, Base):
    """组织成员关系。

    role: owner（创建者）/ admin（组织管理员）/ member
    status: pending（待组织管理员审核）/ active / rejected / left
    """

    __tablename__ = "org_memberships"
    __table_args__ = (
        UniqueConstraint("org_id", "user_id", name="uq_org_user"),
    )

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String(16), default="member")  # owner / admin / member
    status = Column(String(16), default="pending", index=True)  # pending / active / rejected / left
    handled_by = Column(Integer, default=0)
    handle_note = Column(String(255), default="")
    handled_at = Column(DateTime, nullable=True)

    org = relationship("Organization", back_populates="memberships")
    user = relationship("User", foreign_keys=[user_id])

    @property
    def is_org_admin(self) -> bool:
        return self.role in ("owner", "admin") and self.status == "active"

    def to_dict(self):
        return {
            "id": self.id,
            "org_id": self.org_id,
            "user_id": self.user_id,
            "nickname": self.user.nickname if self.user else "",
            "grade_class": self.user.grade_class if self.user else "",
            "avatar": self.user.avatar if self.user else "",
            "role": self.role,
            "status": self.status,
            "handle_note": self.handle_note or "",
            "handled_at": self.handled_at.strftime("%Y-%m-%d %H:%M") if self.handled_at else "",
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else "",
            "org_name": self.org.name if self.org else "",
            "org_status": self.org.status if self.org else "",
            "org_type": self.org.org_type if self.org else "",
            "invite_code": self.org.invite_code if self.org and self.is_org_admin else "",
        }


class Item(TimestampMixin, Base):
    __tablename__ = "items"
    __table_args__ = (
        CheckConstraint("value_coins >= 0", name="ck_item_value_nonneg"),
    )

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    name = Column(String(64), nullable=False)
    category = Column(String(32), nullable=False)
    description = Column(Text, default="")
    images = Column(String(500), default="")      # 逗号分隔的图片 URL 列表
    condition = Column(String(16), default="九成新")
    value_coins = Column(Integer, default=0)      # AI 傍议参考枚数（非价格）
    want_tags = Column(String(255), default="")   # 想换什么，逗号分隔
    status = Column(String(16), default="on_shelf")  # on_shelf / swapping / swapped / off_shelf / reported / removed
    reported = Column(Integer, default=0)              # 被举报次数（>0 即出现在待办中）
    flagged = Column(Boolean, default=False)           # 是否已被标记（前端可见角标）
    removed_reason = Column(String(255), default="")  # 管理员下架原因
    removed_by = Column(Integer, default=0)            # 处理管理员 user.id

    owner = relationship("User", back_populates="items")
    org = relationship("Organization", foreign_keys=[org_id])
    reports = relationship("Report", back_populates="item", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "org_id": self.org_id or 0,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "images": [img for img in self.images.split(",") if img],
            "condition": self.condition,
            "value_coins": self.value_coins,
            "want_tags": [t for t in self.want_tags.split(",") if t],
            "status": self.status,
            "reported": self.reported,
            "flagged": self.flagged,
            "removed_reason": self.removed_reason,
            "owner": self.owner.nickname if self.owner else "",
            "owner_class": self.owner.grade_class if self.owner else "",
        }


class Swap(TimestampMixin, Base):
    """一次交换请求（以物换物，全程零金钱）。

    状态机：
      pending_parent -> pending_peer -> accepted -> completed
                         \-> cancelled
    每一步家长的确认动作都有记录，保证责任链清晰。
    """

    __tablename__ = "swaps"

    id = Column(Integer, primary_key=True, index=True)
    initiator_item_id = Column(
        Integer, ForeignKey("items.id"), nullable=False, index=True
    )
    receiver_item_id = Column(
        Integer, ForeignKey("items.id"), nullable=False, index=True
    )
    status = Column(String(24), default="pending_parent", index=True)
    note = Column(Text, default="")               # 交换留言

    # 家长确认位（两个家长都要点头）
    initiator_parent_confirmed = Column(Boolean, default=False)
    receiver_parent_confirmed = Column(Boolean, default=False)
    # 完成确认位（双方点“交换完成”，第二方确认时结算咸鱼币）
    initiator_parent_completed = Column(Boolean, default=False)
    receiver_parent_completed = Column(Boolean, default=False)

    completed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    cancel_reason = Column(String(255), default="")

    initiator_item = relationship(
        "Item", foreign_keys=[initiator_item_id], backref="swaps_initiated"
    )
    receiver_item = relationship(
        "Item", foreign_keys=[receiver_item_id], backref="swaps_received"
    )

    # ---- 业务辅助 -------------------------------------------------------
    @property
    def initiator(self) -> "User":
        return self.initiator_item.owner

    @property
    def receiver(self) -> "User":
        return self.receiver_item.owner

    def to_dict(self):
        return {
            "id": self.id,
            "status": self.status,
            "note": self.note,
            "initiator_item": self.initiator_item.to_dict(),
            "receiver_item": self.receiver_item.to_dict(),
            "initiator_parent_confirmed": self.initiator_parent_confirmed,
            "receiver_parent_confirmed": self.receiver_parent_confirmed,
            "initiator_parent_completed": self.initiator_parent_completed,
            "receiver_parent_completed": self.receiver_parent_completed,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M")
            if self.created_at
            else "",
            "completed_at": self.completed_at.strftime("%Y-%m-%d %H:%M")
            if self.completed_at
            else "",
        }


class CoinLedger(TimestampMixin, Base):
    """咸鱼币流水（积分台账）。只记录系统规则发放，杜绝用户间转移。"""

    __tablename__ = "coin_ledger"
    __table_args__ = (
        UniqueConstraint("user_id", "source_type", "source_id", name="uq_ledger_source"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    delta = Column(Integer, nullable=False)         # 正负
    balance_after = Column(Integer, nullable=False) # 结算后余额（审计用）
    source_type = Column(String(32), nullable=False)  # register / list_item / swap_complete / swap_cancel
    source_id = Column(Integer, nullable=False, default=0)
    note = Column(String(255), default="")

    def to_dict(self):
        return {
            "id": self.id,
            "delta": self.delta,
            "balance_after": self.balance_after,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "note": self.note,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M")
            if self.created_at
            else "",
        }


class Category(TimestampMixin, Base):
    """闲置分类（数据库可配置，管理员后台增删改）。

    分类名、AI 估值默认枚数、排序、启停 都由管理员在后台维护，
    替代之前写死在 config.py 的 ITEM_CATEGORIES。
    """

    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(32), unique=True, nullable=False)     # 分类名
    value_base = Column(Integer, default=2)                     # AI 估值参考枚数基准
    note = Column(String(255), default="")                      # 说明（估值副文案）
    sort_order = Column(Integer, default=0)                     # 排序（越小越靠前）
    is_active = Column(Boolean, default=True)                    # 停用后发布不可选

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "value_base": self.value_base,
            "note": self.note,
            "sort_order": self.sort_order,
            "is_active": self.is_active,
        }


class Report(TimestampMixin, Base):
    """举报单：家长/游客对某件闲置的举报，管理员来处理。

    状态机：
      pending   -> resolved  （管理员下架 / 保留但记录）
                 -> rejected  （管理员驳回，认定无违规）

    物品被举报后 flagged=True 并在列表下沉展示，管理员可在后台处理。
    """

    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False, index=True)
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # 举报人
    reporter_note = Column(Text, default="")        # 举报人自由备注
    reason = Column(String(32), nullable=False)     # 固定理由枚举（见 config.REPORT_REASONS）
    status = Column(String(16), default="pending", index=True)  # pending / resolved / rejected
    handled_by = Column(Integer, default=0)          # 处理管理员 user.id
    handle_note = Column(String(255), default="")   # 管理员处理说明
    handled_at = Column(DateTime, nullable=True)

    item = relationship("Item", back_populates="reports")
    reporter = relationship("User", foreign_keys=[reporter_id])

    def to_dict(self):
        return {
            "id": self.id,
            "item_id": self.item_id,
            "reporter_id": self.reporter_id,
            "reporter_name": self.reporter.nickname if self.reporter else "",
            "reason": self.reason,
            "reporter_note": self.reporter_note,
            "status": self.status,
            "handled_by": self.handled_by,
            "handle_note": self.handle_note,
            "handled_at": self.handled_at.strftime("%Y-%m-%d %H:%M")
            if self.handled_at
            else "",
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M")
            if self.created_at
            else "",
            "item": self.item.to_dict() if self.item else None,
        }


class LlmProvider(TimestampMixin, Base):
    """大模型 API 配置（多 Key / 多厂商，免费额度挂了可切下一家）。

    统一按 OpenAI 兼容协议调用 /chat/completions。
    """

    __tablename__ = "llm_providers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), nullable=False)                 # 显示名，如「硅基流动-免费1」
    vendor = Column(String(32), default="openai")             # openai / deepseek / siliconflow / moonshot / zhipu / custom
    base_url = Column(String(255), nullable=False)            # 如 https://api.openai.com/v1
    api_key = Column(String(255), nullable=False, default="")
    model = Column(String(64), nullable=False, default="gpt-4o-mini")
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)                   # 越小越优先
    timeout_sec = Column(Integer, default=30)
    note = Column(String(255), default="")
    last_error = Column(String(255), default="")
    last_ok_at = Column(DateTime, nullable=True)
    fail_count = Column(Integer, default=0)

    def masked_key(self) -> str:
        key = self.api_key or ""
        if len(key) <= 8:
            return "****" if key else ""
        return f"{key[:4]}…{key[-4:]}"

    def to_dict(self, *, reveal_key: bool = False):
        return {
            "id": self.id,
            "name": self.name,
            "vendor": self.vendor,
            "base_url": self.base_url,
            "api_key": self.api_key if reveal_key else self.masked_key(),
            "api_key_set": bool(self.api_key),
            "model": self.model,
            "is_active": self.is_active,
            "sort_order": self.sort_order,
            "timeout_sec": self.timeout_sec,
            "note": self.note or "",
            "last_error": self.last_error or "",
            "last_ok_at": self.last_ok_at.strftime("%Y-%m-%d %H:%M") if self.last_ok_at else "",
            "fail_count": self.fail_count or 0,
        }
