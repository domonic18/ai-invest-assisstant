"""工作台聚合响应的 Pydantic schemas。"""

from datetime import date, datetime
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


class ReviewDayStatus(BaseModel):
    """近段交易日单日复盘生成结果。"""

    trade_date: date
    status: Literal["success", "failed", "pending"]


class ReviewStatusResponse(BaseModel):
    """复盘状态卡数据：做没做 / 何时做 / 做得怎样（正文不在工作台展示）。"""

    status: Literal["done", "pending", "failed"]
    trade_date: date
    generated_at: datetime | None = None
    duration_seconds: int | None = None
    planned_time: str | None = None
    next_run_at: datetime | None = None
    streak_days: int = 0
    month_success_rate: float | None = None
    recent_days: list[ReviewDayStatus] = []


class CollectorRunItem(BaseModel):
    """采集引擎最近一条运行记录。"""

    task_name: str
    task_label: str
    source: str | None = None
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: int | None = None
    records_count: int | None = None


class CollectorUpcomingItem(BaseModel):
    """采集引擎未来计划中的一次运行。"""

    run_at: datetime
    task_name: str
    task_label: str
    source: str | None = None


class CollectorStatusResponse(BaseModel):
    """采集引擎状态卡数据：是否在跑 / 接下来半天跑什么 / 最近跑得怎样。"""

    is_running: bool = False
    running: CollectorRunItem | None = None
    recent_runs: list[CollectorRunItem] = []
    upcoming: list[CollectorUpcomingItem] = []


class WorkbenchResponse(BaseModel):
    """工作台聚合数据；单模块降级时对应字段为空态而非整体报错。"""

    calendar: list[CalendarEventResponse] = []
    review: MarketReviewResponse | None = None
    review_status: ReviewStatusResponse | None = None
    telegraph: list[TelegraphResponse] = []
    watchlist_groups: list[WorkbenchWatchlistGroup] = []
    indices: list[IndexQuoteResponse] = []
    stats: MarketStatsResponse | None = None
    global_indices: list[GlobalIndexQuoteResponse] = []
    sector_flow: list[SectorFlowItem] = []
    collector_status: CollectorStatusResponse | None = None
