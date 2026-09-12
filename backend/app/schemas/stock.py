"""股票行情数据相关的 Pydantic schemas。"""

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from app.schemas.base import CamelModel


class StockBasicResponse(CamelModel):
    """股票基础信息响应。"""

    id: int
    stock_code: str
    stock_name: str
    market: str
    industry_level_1: str | None = None
    industry_level_2: str | None = None
    industry_level_3: str | None = None
    listing_date: date | None = None
    total_shares: int | None = None
    circulating_shares: int | None = None
    full_name: str | None = None
    legal_person: str | None = None
    website: str | None = None
    registered_capital: float | None = None
    business_scope: str | None = None
    province: str | None = None
    city: str | None = None


class StockSearchRequest(CamelModel):
    """股票搜索请求。"""

    q: str = Field(..., min_length=1, max_length=50)
    limit: int = Field(default=20, ge=1, le=100)


class AdminStockCreate(CamelModel):
    """后台创建股票请求。"""

    stock_code: str = Field(..., min_length=6, max_length=10)
    stock_name: str = Field(..., max_length=50)
    market: str = Field(..., pattern="^(sh|sz|bj)$")
    industry_level_1: str | None = Field(None, max_length=50)
    industry_level_2: str | None = Field(None, max_length=50)
    industry_level_3: str | None = Field(None, max_length=50)
    listing_date: date | None = None


class AdminStockUpdate(CamelModel):
    """后台更新股票请求。"""

    stock_name: str | None = Field(None, max_length=50)
    market: str | None = Field(None, pattern="^(sh|sz|bj)$")
    industry_level_1: str | None = Field(None, max_length=50)
    industry_level_2: str | None = Field(None, max_length=50)
    industry_level_3: str | None = Field(None, max_length=50)
    listing_date: date | None = None


class KlineDataResponse(CamelModel):
    """日 K 线数据响应。"""

    trade_date: date
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None
    amount: float | None = None
    amplitude: float | None = None
    change_pct: float | None = None
    turnover_rate: float | None = None


class StockQuoteResponse(CamelModel):
    """个股实时行情快照响应。"""

    code: str
    name: str
    price: float | None = None
    prev_close: float | None = None
    change: float | None = None
    change_pct: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    volume: int | None = None
    amount: float | None = None
    market_cap: float | None = None
    circulating_market_cap: float | None = None
    updated_at: str | None = None


class StockKlineBar(CamelModel):
    """个股 K 线单根 bar。"""

    date: date
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None
    amount: float | None = None
    change_pct: float | None = None
    amplitude: float | None = None
    turnover_rate: float | None = None


class StockKlineResponse(CamelModel):
    """个股多周期 K 线响应。"""

    code: str
    name: str
    period: str
    bars: list[StockKlineBar]
    # 最近交易日（交易日历权威），前端据此判定 K 线是否落后并自动补采
    latest_trade_date: date


class StockIntradayPoint(CamelModel):
    """个股分时单点。"""

    time: str
    price: float
    volume: int
    amount: float


class StockIntradayResponse(CamelModel):
    """个股分时响应。"""

    code: str
    name: str
    trade_date: date
    prev_close: float
    points: list[StockIntradayPoint]


class StockSectorItem(CamelModel):
    """个股所属板块/概念项。"""

    name: str
    type: Literal["industry", "concept"]
    change_pct: float | None = None
    main_net_inflow: float | None = None


class StockSectorsResponse(CamelModel):
    """个股所属板块与概念响应。"""

    code: str
    name: str
    sectors: list[StockSectorItem]


class StockAiAnalysisSection(CamelModel):
    """个股 AI 分析单分区内容。"""

    key: str
    title: str
    content: str


class StockAiAnalysisResponse(CamelModel):
    """个股每日 AI 分析响应。"""

    stock_code: str
    stock_name: str
    trade_date: date
    model: str | None = None
    generated_at: datetime
    cached: bool = False
    sections: list[StockAiAnalysisSection]


class StockAiAnalysisStatusResponse(CamelModel):
    """个股 AI 分析异步状态响应（轮询契约）。

    ready 时 data 必非空；running 表示生成任务进行中；none 表示无缓存且
    无进行中的生成。trade_date 是本次查询实际采用的有效交易日
    （缺省=最近交易日；显式非交易日归位到不晚于该日的最近交易日）。
    """

    status: Literal["running", "ready", "none"]
    data: StockAiAnalysisResponse | None = None
    trade_date: date


class StockAiAnalysisDatesResponse(CamelModel):
    """个股已生成分析的全部交易日（升序），供前端日历标记。"""

    code: str
    trade_dates: list[date]


class PaginationParams(CamelModel):
    """通用分页参数。"""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class PaginatedResponse(CamelModel):
    """通用分页响应。"""

    total: int
    page: int
    page_size: int
    items: list
