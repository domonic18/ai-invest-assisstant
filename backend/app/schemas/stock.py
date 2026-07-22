"""Stock market data related Pydantic schemas."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class StockBasicResponse(BaseModel):
    """股票基础信息响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_code: str
    stock_name: str
    market: str
    industry_l1: str | None = None
    industry_l2: str | None = None
    industry_l3: str | None = None
    listing_date: date | None = None
    total_shares: int | None = None
    circulating_shares: int | None = None
    full_name: str | None = None
    legal_person: str | None = None
    website: str | None = None
    registered_capital: Decimal | None = None
    business_scope: str | None = None
    province: str | None = None
    city: str | None = None


class StockSearchRequest(BaseModel):
    """股票搜索请求。"""

    q: str = Field(..., min_length=1, max_length=50)
    limit: int = Field(default=20, ge=1, le=100)


class AdminStockCreate(BaseModel):
    """后台创建股票请求。"""

    stock_code: str = Field(..., min_length=6, max_length=10)
    stock_name: str = Field(..., max_length=50)
    market: str = Field(..., pattern="^(sh|sz|bj)$")
    industry_l1: str | None = Field(None, max_length=50)
    industry_l2: str | None = Field(None, max_length=50)
    industry_l3: str | None = Field(None, max_length=50)
    listing_date: date | None = None


class AdminStockUpdate(BaseModel):
    """后台更新股票请求。"""

    stock_name: str | None = Field(None, max_length=50)
    market: str | None = Field(None, pattern="^(sh|sz|bj)$")
    industry_l1: str | None = Field(None, max_length=50)
    industry_l2: str | None = Field(None, max_length=50)
    industry_l3: str | None = Field(None, max_length=50)
    listing_date: date | None = None


class KlineDataResponse(BaseModel):
    """日 K 线数据响应。"""

    model_config = ConfigDict(from_attributes=True)

    trade_date: date
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    close: Decimal | None = None
    volume: int | None = None
    amount: Decimal | None = None
    amplitude: Decimal | None = None
    pct_change: Decimal | None = None
    turnover_rate: Decimal | None = None


class AuctionDataResponse(BaseModel):
    """集合竞价数据响应。"""

    model_config = ConfigDict(from_attributes=True)

    trade_date: date
    match_time: datetime
    price: Decimal | None = None
    volume: int | None = None
    bid_prices: list[Decimal | None] | None = None
    bid_volumes: list[int | None] | None = None
    ask_prices: list[Decimal | None] | None = None
    ask_volumes: list[int | None] | None = None


class IndexAuctionSeries(BaseModel):
    """单个指数的集合竞价成交额序列（亿元，与 dates 逐点对齐，缺数据为 None）。"""

    code: str
    name: str
    values: list[float | None]


class IndexAuctionTrendResponse(BaseModel):
    """指数集合竞价成交额趋势（dates 升序）。"""

    dates: list[date]
    series: list[IndexAuctionSeries]


class FundFlowResponse(BaseModel):
    """资金流向数据响应。"""

    model_config = ConfigDict(from_attributes=True)

    stock_code: str
    trade_date: date
    main_net_inflow: Decimal | None = None
    super_large_net: Decimal | None = None
    large_net: Decimal | None = None
    medium_net: Decimal | None = None
    small_net: Decimal | None = None


class PaginationParams(BaseModel):
    """通用分页参数。"""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class PaginatedResponse(BaseModel):
    """通用分页响应。"""

    total: int
    page: int
    page_size: int
    items: list
