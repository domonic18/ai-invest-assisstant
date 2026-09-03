"""市场总览（每日复盘）API 的 Pydantic schemas。"""

from datetime import date, datetime

from pydantic import BaseModel, Field


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


class IndexKlineBar(BaseModel):
    """指数 K 线单根 bar（日线或聚合周期）。"""

    date: date
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None
    amount: float | None = None


class IndexKlineResponse(BaseModel):
    """指数多周期 K 线（日/周/月/季/年，由本地 quote_kline_stock_daily 聚合）。"""

    code: str
    name: str
    period: str
    bars: list[IndexKlineBar]


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
    broken_limit_count: int | None = None
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
    broken_limit_count: int | None = None
    limit_status: str | None = None
    consecutive_boards: int | None = None
    industry: str | None = None
    seal_type: str | None = None  # 一字板 / T字板 / None（开盘涨停推导）
    themes: list[str] = []  # AI 归因的题材标签（1-3 个短词）


class LimitUpGroup(BaseModel):
    """涨停复盘分组（行业分组或 AI 题材分组）。"""

    name: str  # 行业名或 AI 题材名
    count: int
    change_pct: float | None = None
    main_net_inflow: float | None = None
    reason: str | None = None  # AI 归因的涨停原因描述
    items: list[LimitUpItem] = []


class LimitUpResponse(BaseModel):
    """涨停板与连板天梯。"""

    trade_date: date
    total: int = 0
    first_board: int = 0
    continuous: int = 0
    max_boards: int | None = None
    ladder: list[LimitUpItem] = []
    items: list[LimitUpItem] = []
    groups: list[LimitUpGroup] = []
    ai_generated: bool = False  # groups 是否为 AI 题材归因分组


class LimitUpIntradayResponse(BaseModel):
    """涨停个股全天分时缩略图数据（每股 ≤60 个收盘价等距采样点）。"""

    trade_date: date
    series: dict[str, list[float]] = {}


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
    trend: list[float] = []


class MarketReviewSection(BaseModel):
    """AI 复盘的一个内容分区（key 与标题由 prompt YAML 的 sections 声明驱动）。"""

    key: str
    title: str
    content: str


class MarketReviewResponse(BaseModel):
    """AI 大盘综述（LLM 结构化输出，按分区组织）。"""

    trade_date: date
    sections: list[MarketReviewSection]
    model: str | None = None
    generated_at: datetime
    cached: bool = False
    edited: bool = False


class MarketReviewGenerateRequest(BaseModel):
    """触发 AI 复盘生成请求。"""

    trade_date: date | None = None
    regenerate: bool = False


class MarketReviewUpdateRequest(BaseModel):
    """按分区保存人工编辑后的复盘内容。"""

    trade_date: date
    section_key: str = Field(min_length=1)
    content: str = Field(min_length=1)


class MarketCollectRequest(BaseModel):
    """补采指定交易日行情数据请求。"""

    trade_date: date


class CollectTaskResult(BaseModel):
    """单个采集任务的补采结果。"""

    task: str
    status: str
    items_collected: int
    errors: list[str] = []
