"""工作台聚合响应的 Pydantic schemas。"""

from typing import Literal

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


class WorkbenchWatchlistStock(WatchlistQuoteItem):
    """自选股概览行：行情快照 + 所属分组开启 AI 复盘时的分析状态与摘要。"""

    ai_status: Literal["off", "pending", "ready"] = "off"
    ai_summary: str | None = None


class WorkbenchWatchlistGroup(BaseModel):
    """工作台自选股概览的分组容器。"""

    id: int
    name: str
    is_default: bool = False
    ai_review_enabled: bool = False
    items: list[WorkbenchWatchlistStock] = []


class SectorFlowItem(BaseModel):
    """板块资金动向卡单行：最新交易日主力净流入排行（金额单位亿元）。"""

    sector_name: str
    change_pct: float | None = None
    main_net_inflow: float | None = None
    top_stock_name: str | None = None


class WorkbenchResponse(BaseModel):
    """工作台六模块聚合数据；单模块降级时对应字段为空态而非整体报错。"""

    calendar: list[CalendarEventResponse] = []
    review: MarketReviewResponse | None = None
    telegraph: list[TelegraphResponse] = []
    watchlist_groups: list[WorkbenchWatchlistGroup] = []
    indices: list[IndexQuoteResponse] = []
    stats: MarketStatsResponse | None = None
    global_indices: list[GlobalIndexQuoteResponse] = []
    sector_flow: list[SectorFlowItem] = []
