"""跟踪指数配置管理的 Pydantic schemas。"""

from datetime import date, datetime

from pydantic import Field

from app.schemas.base import CamelModel


class TrackedIndexCreate(CamelModel):
    """创建跟踪指数配置的请求 schema。"""

    index_code: str = Field(..., min_length=1, max_length=16)
    index_name: str = Field(..., min_length=1, max_length=100)
    market_category: str = Field(..., min_length=1, max_length=10)
    data_source: str = Field(..., min_length=1, max_length=50)
    sort_order: int = 100
    is_enabled: bool = True


class TrackedIndexUpdate(CamelModel):
    """更新跟踪指数配置的请求 schema。"""

    index_name: str | None = Field(None, min_length=1, max_length=100)
    market_category: str | None = Field(None, min_length=1, max_length=10)
    data_source: str | None = Field(None, min_length=1, max_length=50)
    sort_order: int | None = None
    is_enabled: bool | None = None


class TrackedIndexResponse(CamelModel):
    """跟踪指数配置的响应 schema（含最新行情联查结果）。"""

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


class TrackedIndexToggleResponse(CamelModel):
    """启用状态切换的响应 schema。"""

    id: int
    is_enabled: bool


class TrackedIndexOption(CamelModel):
    """个人设置中可勾选的跟踪指数项（附分类与最新行情预览）。"""

    id: int
    index_code: str
    index_name: str
    market_category: str
    latest_close: float | None = None
    latest_change_pct: float | None = None
    latest_trade_date: date | None = None
