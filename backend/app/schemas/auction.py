"""集合竞价相关的 Pydantic schemas。

金额字段用 float 而非 Decimal：Pydantic v2 会把 Decimal 序列化成
JSON 字符串，违背 shared 契约声明的 number 类型。
"""

from datetime import date, time

from app.schemas.base import CamelModel


class AuctionDataResponse(CamelModel):
    """集合竞价数据响应。"""

    trade_date: date
    match_time: time
    price: float | None = None
    volume: int | None = None
    bid_prices: list[float | None] | None = None
    bid_volumes: list[int | None] | None = None
    ask_prices: list[float | None] | None = None
    ask_volumes: list[int | None] | None = None


class IndexAuctionSeries(CamelModel):
    """单个指数的集合竞价成交额序列（亿元，与 dates 逐点对齐，缺数据为 None）。"""

    code: str
    name: str
    values: list[float | None]


class IndexAuctionTrendResponse(CamelModel):
    """指数集合竞价成交额趋势（dates 升序）。"""

    dates: list[date]
    series: list[IndexAuctionSeries]
