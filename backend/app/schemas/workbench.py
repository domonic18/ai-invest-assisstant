"""工作台聚合响应的 Pydantic schemas。"""

from pydantic import BaseModel

from app.schemas.calendar import CalendarEventResponse
from app.schemas.market import (
    GlobalIndexQuoteResponse,
    IndexQuoteResponse,
    MarketReviewResponse,
    MarketStatsResponse,
    WatchlistQuoteItem,
)
from app.schemas.telegraph import TelegraphResponse


class WorkbenchResponse(BaseModel):
    """工作台五模块聚合数据；单模块降级时对应字段为空态而非整体报错。"""

    calendar: list[CalendarEventResponse] = []
    review: MarketReviewResponse | None = None
    telegraph: list[TelegraphResponse] = []
    watchlist: list[WatchlistQuoteItem] = []
    indices: list[IndexQuoteResponse] = []
    stats: MarketStatsResponse | None = None
    global_indices: list[GlobalIndexQuoteResponse] = []
