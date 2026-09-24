"""模拟盘 API 的 Pydantic schemas（camelCase wire，金额一律 float）。"""

from datetime import date, datetime

from app.schemas.base import CamelModel


class PaperTradeCashInfo(CamelModel):
    """资金概况（sidecar 实时透传）。"""

    nav: float | None = None
    available: float | None = None
    balance: float | None = None
    cum_inout: float | None = None
    last_inout: float | None = None


class PaperTradePositionRow(CamelModel):
    """持仓行（柜台字段以实抓为准，缺失项为 None，前端渲染 '-'）。"""

    symbol: str = ""
    stock_code: str = ""
    side: int | None = None
    volume: int | None = None
    available_volume: int | None = None
    avg_price: float | None = None
    last_price: float | None = None
    market_value: float | None = None
    profit: float | None = None
    profit_rate: float | None = None


class PaperTradeOrderRow(CamelModel):
    """委托行（本地表或 sidecar 未结委托）。"""

    cl_ord_id: str
    trade_date: date
    symbol: str
    stock_code: str
    side: int
    order_type: int
    position_effect: int
    price: float
    volume: int
    status: int
    ord_rej_reason: int | None = None
    ord_rej_reason_detail: str | None = None
    counter_created_at: datetime | None = None
    counter_updated_at: datetime | None = None


class PaperTradeExecutionRow(CamelModel):
    """成交回报行（本地表）。"""

    exec_id: str
    cl_ord_id: str
    trade_date: date
    symbol: str
    side: int | None = None
    exec_type: int | None = None
    price: float | None = None
    volume: int | None = None
    turnover: float | None = None
    commission: float | None = None
    counter_created_at: datetime | None = None


class PaperTradeOverviewResponse(CamelModel):
    """模拟盘总览：enabled=false 表示模拟盘功能未配置（前端展示引导卡）。"""

    enabled: bool = True
    cash: PaperTradeCashInfo | None = None
    positions: list[PaperTradePositionRow] = []
    unfinished_orders: list[PaperTradeOrderRow] = []


class PaperTradeNavPoint(CamelModel):
    """净值曲线单点。"""

    trade_date: date
    nav: float | None = None
    available: float | None = None


class PaperTradeNavResponse(CamelModel):
    """净值曲线（trade_date 升序）。"""

    items: list[PaperTradeNavPoint] = []


class PaperTradeOrderPageResponse(CamelModel):
    """委托分页（带业务日回显，前端标题展示）。"""

    total: int
    page: int
    page_size: int
    trade_date: date
    items: list[PaperTradeOrderRow] = []


class PaperTradeExecutionPageResponse(CamelModel):
    """成交回报分页（带业务日回显）。"""

    total: int
    page: int
    page_size: int
    trade_date: date
    items: list[PaperTradeExecutionRow] = []
