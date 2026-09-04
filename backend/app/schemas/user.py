"""用户与自选股相关的 Pydantic schemas。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MovingAverageConfig(BaseModel):
    """单条均线配置。"""

    period: int = Field(..., ge=1, le=500, description="均线周期（日）")
    color: str = Field(..., pattern=r"^#[0-9a-fA-F]{6}$", description="十六进制颜色")
    enabled: bool = Field(default=True, description="是否显示")


class UserSettings(BaseModel):
    """用户个人配置。"""

    # 服务层返回 UserSettings 实例，路由层需跨模型 model_validate
    model_config = ConfigDict(from_attributes=True)

    ma_configs: list[MovingAverageConfig] = Field(
        default_factory=list,
        description="K 线均线配置列表",
    )


class UserSettingsResponse(UserSettings):
    """用户配置响应模型。"""

    pass


class UserSettingsUpdate(UserSettings):
    """更新用户配置请求。"""

    pass


class UserResponse(BaseModel):
    """用户响应模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    role: str
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime


class AdminUserCreate(BaseModel):
    """后台创建用户请求。"""

    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., max_length=100)
    password: str = Field(..., min_length=6, max_length=100)
    role: str = Field(default="user", pattern="^(user|admin|analyst)$")
    is_active: bool = True


class AdminUserUpdate(BaseModel):
    """后台更新用户请求。"""

    username: str | None = Field(None, min_length=3, max_length=50)
    email: str | None = Field(None, max_length=100)
    role: str | None = Field(None, pattern="^(user|admin|analyst)$")
    is_active: bool | None = None


class AdminUserResetPassword(BaseModel):
    """后台重置密码请求。"""

    password: str = Field(..., min_length=6, max_length=100)


class WatchlistItemCreate(BaseModel):
    """自选股创建请求。"""

    stock_code: str = Field(..., min_length=6, max_length=10)
    tags: list[str] | None = None
    group_id: int | None = Field(None, description="目标分组，缺省挂默认分组")


class WatchlistScreenshotRecognitionItem(BaseModel):
    """截图识别结果单项（已与 stock_basic 交叉校验）。"""

    stock_code: str
    stock_name: str | None = Field(None, description="识别名称；命中库内时为标准简称")
    confidence: float | None = None
    valid: bool = Field(False, description="代码/名称命中 stock_basic")
    matched_name: str | None = Field(None, description="库内标准简称（valid 时返回）")


class WatchlistScreenshotRecognitionResponse(BaseModel):
    """截图识别响应。"""

    items: list[WatchlistScreenshotRecognitionItem]


class WatchlistBatchItemCreate(BaseModel):
    """自选股批量导入单项。"""

    stock_code: str = Field(..., min_length=6, max_length=10)
    tags: list[str] | None = None


class WatchlistBatchCreate(BaseModel):
    """自选股批量导入请求：二选一指定目标分组。"""

    items: list[WatchlistBatchItemCreate] = Field(..., min_length=1, max_length=50)
    group_id: int | None = None
    new_group_name: str | None = Field(None, min_length=1, max_length=50)


class WatchlistBatchDuplicatedItem(BaseModel):
    """批量导入时已存在的股票。"""

    stock_code: str
    group_id: int | None = None
    group_name: str | None = None


class WatchlistItemResponse(BaseModel):
    """自选股响应模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_code: str
    tags: list[str] | None = None
    group_id: int
    created_at: datetime


class WatchlistBatchResponse(BaseModel):
    """自选股批量导入响应。"""

    created: list[WatchlistItemResponse] = []
    duplicated: list[WatchlistBatchDuplicatedItem] = []
    invalid: list[str] = []


class WatchlistGroupCreate(BaseModel):
    """自选股分组创建请求。"""

    name: str = Field(..., min_length=1, max_length=50)
    ai_review_enabled: bool = False


class WatchlistGroupUpdate(BaseModel):
    """自选股分组更新请求。"""

    name: str | None = Field(None, min_length=1, max_length=50)
    ai_review_enabled: bool | None = None


class WatchlistGroupResponse(BaseModel):
    """自选股分组响应模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sort_order: int
    is_default: bool
    ai_review_enabled: bool
    created_at: datetime


class WatchlistGroupWithItemsResponse(WatchlistGroupResponse):
    """带组内股票的分组响应模型。"""

    items: list[WatchlistItemResponse] = []


class WatchlistGroupReorderRequest(BaseModel):
    """分组整体排序请求（group_ids 顺序即新顺序）。"""

    group_ids: list[int] = Field(..., min_length=1)


class WatchlistItemMoveRequest(BaseModel):
    """自选股移动分组请求。"""

    group_id: int
