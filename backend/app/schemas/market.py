"""Pydantic schemas for market overview (每日复盘) APIs."""

from datetime import date, datetime

from pydantic import BaseModel


class IndexQuoteResponse(BaseModel):
    """大盘指数行情。"""

    code: str
    name: str
    price: float
    change: float
    change_pct: float
    amount: float | None = None
    trend: list[float] = []


class IndexIntradayPoint(BaseModel):
    """指数分时数据点（1 分钟）。"""

    time: str
    price: float
    volume: float
    amount: float


class IndexIntradayResponse(BaseModel):
    """指数分时图（最近一个交易日的分钟级行情与量能）。"""

    code: str
    name: str
    trade_date: date
    prev_close: float
    points: list[IndexIntradayPoint]


class MarketStatsResponse(BaseModel):
    """市场涨跌与成交统计，含情绪温度。"""

    trade_date: date
    amount: float | None = None
    prev_amount: float | None = None
    amount_change: float | None = None
    amount_change_pct: float | None = None
    up_count: int | None = None
    down_count: int | None = None
    flat_count: int | None = None
    limit_up_count: int = 0
    limit_down_count: int = 0
    broken_count: int | None = None
    emotion_score: float | None = None
    emotion_label: str | None = None
    limit_up_ratio: float | None = None
    continuous_rate: float | None = None
    broken_rate: float | None = None


class LimitUpItem(BaseModel):
    """涨停股池条目。"""

    stock_code: str
    stock_name: str | None = None
    change_pct: float | None = None
    latest_price: float | None = None
    sealed_amount: float | None = None
    first_seal_time: str | None = None
    last_seal_time: str | None = None
    break_count: int | None = None
    limit_stat: str | None = None
    consecutive_boards: int | None = None
    industry: str | None = None


class LimitUpResponse(BaseModel):
    """涨停板与连板天梯。"""

    trade_date: date
    total: int = 0
    first_board: int = 0
    continuous: int = 0
    max_boards: int | None = None
    ladder: list[LimitUpItem] = []
    items: list[LimitUpItem] = []


class SectorHeatItem(BaseModel):
    """板块热力图单元。"""

    sector_name: str
    change_pct: float | None = None


class SectorFlowItem(BaseModel):
    """板块资金净流入/流出条目。"""

    sector_name: str
    main_net_inflow: float | None = None
    top_stock_name: str | None = None


class LeadingSectorItem(BaseModel):
    """领涨板块条目。"""

    sector_name: str
    change_pct: float | None = None
    limit_up_count: int = 0
    main_net_inflow: float | None = None
    top_stock_names: list[str] = []


class SectorOverviewResponse(BaseModel):
    """板块热力图 + 资金 TOP5 + 领涨板块。"""

    trade_date: date
    heatmap: list[SectorHeatItem] = []
    top_inflow: list[SectorFlowItem] = []
    top_outflow: list[SectorFlowItem] = []
    leading: list[LeadingSectorItem] = []


class WatchlistQuoteItem(BaseModel):
    """自选股实时行情。"""

    code: str
    name: str | None = None
    price: float | None = None
    change_pct: float | None = None
    amount: float | None = None
    tags: list[str] = []
    updated_at: str | None = None


class MarketReviewResponse(BaseModel):
    """AI 大盘综述（LLM 结构化输出）。"""

    trade_date: date
    overview: str
    emotion_analysis: str
    capital_analysis: str
    risk_advice: str
    model: str | None = None
    generated_at: datetime
    cached: bool = False
