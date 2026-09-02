"""跟踪指数配置管理的 Pydantic schemas。"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class TrackedIndexCreate(BaseModel):
    """创建跟踪指数配置的请求 schema。"""

    index_code: str = Field(..., min_length=1, max_length=16)
    index_name: str = Field(..., min_length=1, max_length=100)
    market_category: str = Field(..., min_length=1, max_length=10)
    data_source: str = Field(..., min_length=1, max_length=50)
    sort_order: int = 100
    is_enabled: bool = True


class TrackedIndexUpdate(BaseModel):
    """更新跟踪指数配置的请求 schema。"""

    index_name: str | None = Field(None, min_length=1, max_length=100)
    market_category: str | None = Field(None, min_length=1, max_length=10)
    data_source: str | None = Field(None, min_length=1, max_length=50)
    sort_order: int | None = None
    is_enabled: bool | None = None


class TrackedIndexResponse(BaseModel):
    """跟踪指数配置的响应 schema（含最新行情联查结果）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    index_code: str
    index_name: str
    market_category: str
    data_source: str
    sort_order: int
    is_enabled: bool
    latest_close: float | None = None
    latest_change_pct: float | None = None
    latest_trade_date: date | None = None
    created_at: datetime
    updated_at: datetime


class TrackedIndexToggleResponse(BaseModel):
    """启用状态切换的响应 schema。"""

    id: int
    is_enabled: bool
