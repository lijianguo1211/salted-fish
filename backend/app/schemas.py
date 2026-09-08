"""Pydantic 请求/响应模型。"""
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---- 认证 ---------------------------------------------------------------
class LoginRequest(BaseModel):
    code: str = ""                    # wx.login() 的 code（演示模式可为设备标识）
    nickname: str = Field("", max_length=32)  # 可选；完善资料在后续步骤
    grade_class: str = Field("", max_length=32)
    school: str = Field("", max_length=64)


class ProfileUpdate(BaseModel):
    nickname: str = Field(..., min_length=1, max_length=32)
    grade_class: str = Field(..., min_length=1, max_length=32)
    school: str = Field(..., min_length=1, max_length=64)


class UserOut(BaseModel):
    id: int
    nickname: str
    role: str
    is_admin: bool
    school: str
    grade_class: str
    coin_balance: int
    avatar: str
    profile_completed: bool = False
    active_org_id: int = 0
    active_org_name: str = ""

    model_config = ConfigDict(from_attributes=True)


# ---- 物品 ---------------------------------------------------------------
class ItemCreate(BaseModel):
    name: str = Field(..., max_length=64)
    category: str = Field(..., max_length=32)
    description: str = Field("", max_length=500)
    images: List[str] = Field(default_factory=list, max_length=6)
    condition: str = Field("九成新", max_length=16)
    want_tags: List[str] = Field(default_factory=list, max_length=10)
    value_coins: Optional[int] = Field(None, ge=0, le=15)  # 物主自己估值；空则沿用 AI


class ItemUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    images: Optional[List[str]] = None
    condition: Optional[str] = None
    want_tags: Optional[List[str]] = None
    value_coins: Optional[int] = Field(None, ge=0, le=15)
    status: Optional[str] = None


class ItemOut(BaseModel):
    id: int
    owner_id: int
    org_id: int = 0
    name: str
    category: str
    description: str
    images: List[str]
    condition: str
    value_coins: int
    ai_value_coins: int = 0
    want_tags: List[str]
    status: str
    reported: int
    flagged: bool
    removed_reason: str
    owner: str
    owner_class: str

    model_config = ConfigDict(from_attributes=True)


# ---- 交换 ---------------------------------------------------------------
class SwapCreate(BaseModel):
    receiver_item_id: int
    initiator_item_id: int
    note: str = Field("", max_length=200)


class SwapAction(BaseModel):
    action: str  # parent_confirm / parent_deny / cancel / complete
    reason: str = Field("", max_length=200)


class SwapOut(BaseModel):
    id: int
    status: str
    note: str
    initiator_item: ItemOut
    receiver_item: ItemOut
    initiator_parent_confirmed: bool
    receiver_parent_confirmed: bool
    initiator_parent_completed: bool
    receiver_parent_completed: bool
    created_at: str
    completed_at: str

    model_config = ConfigDict(from_attributes=True)


# ---- 咸鱼币 -------------------------------------------------------------
class CoinRuleOut(BaseModel):
    action: str
    delta: int
    note: str


class CoinLedgerOut(BaseModel):
    id: int
    user_id: int
    delta: int
    balance_after: int
    source_type: str
    source_id: int
    note: str
    created_at: str


# ---- AI 定价 ------------------------------------------------------------
class AIPricingIn(BaseModel):
    name: str = Field(..., max_length=64)
    category: str = Field(..., max_length=32)
    description: str = Field("", max_length=300)
    condition: str = Field("九成新", max_length=16)
    image_urls: List[str] = Field(default_factory=list, max_length=6)


class AIPricingOut(BaseModel):
    suggested_coins: int
    source: str
    explanation: str
    confidence: Optional[float] = None


# ---- 举报 & 内容治理 ---------------------------------------------------------
class ReportCreate(BaseModel):
    reason: str = Field(..., max_length=32)      # 固定理由，必须来自 config.REPORT_REASONS
    note: str = Field("", max_length=300)         # 举报人自由备注（可选）


class ReportHandle(BaseModel):
    action: str = Field(..., max_length=16)       # remove（下架封禁）/ reject（驳回）/ keep（仅记录放行）
    reason: str = Field(..., max_length=255)      # 给举报人和物主的处理说明


class ReportOut(BaseModel):
    id: int
    item_id: int
    reporter_id: int
    report_name: str = ""
    reason: str
    note: str = ""
    status: str
    handle_note: str = ""
    created_at: str = ""

    model_config = ConfigDict(from_attributes=True)


# ---- 通用 ---------------------------------------------------------------
class Msg(BaseModel):
    message: str
    data: Optional[dict] = None


# ---- 分类管理 ----
class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=32)
    value_base: int = Field(1, ge=1, le=15)     # AI 估值参考枚数
    note: Optional[str] = ""
    sort_order: int = 0
    is_active: bool = True


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=32)
    value_base: Optional[int] = Field(None, ge=1, le=15)
    note: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


# ---- 组织（平台审核） ----------------------------------------------------
class OrgReviewIn(BaseModel):
    action: str = Field(..., max_length=16)  # approve / reject
    reason: str = Field("", max_length=255)


# ---- 大模型配置 ----------------------------------------------------------
class LlmProviderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    vendor: str = Field("openai", max_length=32)
    base_url: str = Field(..., min_length=8, max_length=255)
    api_key: str = Field("", max_length=255)
    model: str = Field("gpt-4o-mini", min_length=1, max_length=64)
    is_active: bool = True
    sort_order: int = 0
    timeout_sec: int = Field(30, ge=5, le=120)
    support_text: bool = True
    support_image: bool = True         # 多模态 / 视觉输入
    support_audio: bool = False        # 音频输入
    note: Optional[str] = ""


class LlmProviderUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=64)
    vendor: Optional[str] = Field(None, max_length=32)
    base_url: Optional[str] = Field(None, min_length=8, max_length=255)
    api_key: Optional[str] = Field(None, max_length=255)  # 空字符串表示不改；传新值才更新
    model: Optional[str] = Field(None, min_length=1, max_length=64)
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None
    timeout_sec: Optional[int] = Field(None, ge=5, le=120)
    support_text: Optional[bool] = None
    support_image: Optional[bool] = None     # 多模态 / 视觉输入
    support_audio: Optional[bool] = None     # 音频输入
    note: Optional[str] = None
