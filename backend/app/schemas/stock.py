"""Stock market data related Pydantic schemas."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class StockBasicResponse(BaseModel):
    """股票基础信息响应。"""

    model_config = ConfigDict(from_attributes=True)

    stock_code: str
    stock_name: str
    market: str
    industry_l1: str | None = None
    industry_l2: str | None = None
    industry_l3: str | None = None
    listing_date: date | None = None


class StockSearchRequest(BaseModel):
    """股票搜索请求。"""

    q: str = Field(..., min_length=1, max_length=50)
    limit: int = Field(default=20, ge=1, le=100)


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
