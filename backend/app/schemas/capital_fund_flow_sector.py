"""板块资金流向（热点）的 Pydantic schemas。"""

from datetime import date, datetime

from app.schemas.base import CamelModel


class SectorFundFlowResponse(CamelModel):
    """板块资金流向响应。

    金额字段用 float：Pydantic v2 会把 Decimal 序列化成 JSON 字符串，
    违背 shared 契约声明的 number 类型（前端 toFixed 直接崩）。
    """

    sector_code: str
    sector_name: str
    sector_type: str
    trade_date: date
    change_pct: float | None = None
    main_net_inflow: float | None = None
    super_large_net: float | None = None
    large_net: float | None = None
    medium_net: float | None = None
    small_net: float | None = None
    top_stock_code: str | None = None
    top_stock_name: str | None = None
    created_at: datetime


class SectorFlowSeries(CamelModel):
    """单个板块的主力净流入时间序列（亿元，与 dates 对齐，缺口为 None）。"""

    code: str
    name: str
    values: list[float | None]


class SectorFlowTrendResponse(CamelModel):
    """板块资金流向趋势响应：日期升序 + 各板块序列。"""

    dates: list[date]
    sectors: list[SectorFlowSeries]
