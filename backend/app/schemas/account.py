"""账号准入与 AI 用量治理域的 Pydantic schemas（arch/07）。"""

from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.base import CamelModel

# ---- 个人侧 ----


class QuotaResponse(CamelModel):
    """个人配额视图。"""

    total_tokens: int | None = Field(None, description="一次性总量；None = 不设上限")
    used_tokens: int = Field(0, description="系统出口累计消耗")
    remaining_tokens: int | None = Field(None, description="剩余；None = 不限")
    unlimited: bool = False
    byok_enabled: bool = Field(False, description="是否已配置自备 Key")


class UsageItemResponse(CamelModel):
    """单次计量明细。"""

    feature: str
    model_name: str
    outlet: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated: bool
    created_at: datetime


class UsageResponse(CamelModel):
    """个人消耗明细 + 按功能分组汇总。"""

    items: list[UsageItemResponse] = []
    by_feature: dict[str, int] = {}


class UserLlmConfigResponse(CamelModel):
    """BYOK 配置脱敏视图（永不回明文）。"""

    protocol: str
    base_url: str
    model_name: str
    api_key_masked: str


class UserLlmConfigUpsertRequest(CamelModel):
    """保存 BYOK 配置请求（保存前前端先调连通性测试）。"""

    protocol: str = Field(..., pattern="^(openai|anthropic)$")
    base_url: str = Field(..., min_length=1, max_length=255)
    model_name: str = Field(..., min_length=1, max_length=100)
    api_key: str = Field(..., min_length=1, max_length=512)


class LlmConnectionTestResponse(CamelModel):
    """连通性测试结果。"""

    status: str = Field(..., description="success / failed")
    detail: str = ""


# ---- 管理侧 ----


class PendingApplicationResponse(CamelModel):
    """待审申请。"""

    id: int
    username: str
    email: str
    application_note: str | None = None
    created_at: datetime


class ApproveRequest(CamelModel):
    """通过申请请求。"""

    initial_quota_tokens: int | None = Field(None, gt=0, description="初始配额；缺省取全局默认")


class RejectRequest(CamelModel):
    """驳回申请请求（原因必填）。"""

    reason: str = Field(..., min_length=1, max_length=500)


class QuotaAdjustRequest(CamelModel):
    """配额调整请求。"""

    action: str = Field(..., pattern="^(adjust|reset)$")
    delta_tokens: int | None = Field(
        None, description="adjust 必填：正数追加、负数核减"
    )


class QuotaResponseAdmin(CamelModel):
    """用户配额视图（管理端）。"""

    user_id: int
    total_tokens: int | None = None
    remaining_tokens: int | None = None
    unlimited: bool = False


class UsageTrendPoint(CamelModel):
    """看板日趋势点（北京时间日分桶）。"""

    date: str
    total_tokens: int


class UsageTopUser(CamelModel):
    """看板 Top 用户。"""

    user_id: int | None
    username: str | None
    total_tokens: int


class UsagePerUserDailyPoint(CamelModel):
    """成员消耗明细：单日点（北京时间）。"""

    date: str
    total_tokens: int


class UsagePerUserResponse(CamelModel):
    """成员消耗明细行（按用户聚合，对齐大模型平台用量页）。"""

    user_id: int
    username: str | None
    total_tokens: int
    calls: int = Field(0, description="调用次数")
    last_used_at: datetime | None = None
    daily: list[UsagePerUserDailyPoint] = []


class UsageDashboardResponse(CamelModel):
    """全站用量看板。"""

    days: int
    trend_daily: list[UsageTrendPoint] = []
    by_feature: dict[str, int] = {}
    by_model: dict[str, int] = {}
    top_users: list[UsageTopUser] = []
    estimated_ratio: float = 0.0
    exhausted_users: int = 0


class AccountSettingsResponse(CamelModel):
    """账号治理全局设置。"""

    default_quota_tokens: int
    pending_expire_days: int
    admin_exempt: bool


class AccountSettingsUpdateRequest(CamelModel):
    """更新全局设置请求（仅声明的字段生效）。"""

    default_quota_tokens: int | None = Field(None, gt=0)
    pending_expire_days: int | None = Field(None, ge=1, le=365)
    admin_exempt: bool | None = None


class AdminUserRowResponse(CamelModel):
    """用户列表行（含账号状态与用量治理扩展列）。"""

    id: int
    username: str
    email: str
    role: str
    is_active: bool
    status: str
    application_note: str | None = None
    reject_reason: str | None = None
    last_login_at: datetime | None = None
    created_at: datetime
    remaining_quota: int | None = Field(None, description="剩余配额；None = 不限")
    total_used: int = Field(0, description="系统出口累计消耗")
    byok_enabled: bool = False


class GenericResult(CamelModel):
    """通用操作回执。"""

    ok: bool = True
    detail: Any = None
