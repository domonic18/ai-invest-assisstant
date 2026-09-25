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
    order_source: str = "manual"
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


class PaperTradeTradeMarkerRow(CamelModel):
    """B/S/T 图表标记单笔成交（当前用户全账户、按标的过滤，trade_date 升序）。"""

    trade_date: date
    counter_created_at: datetime | None = None
    side: str
    price: float | None = None
    volume: int | None = None


class PaperTradeTradeMarkerResponse(CamelModel):
    """B/S/T 图表标记成交列表。"""

    items: list[PaperTradeTradeMarkerRow] = []


# ============================================================
# 账户配置（多租户）
# ============================================================


class PaperTradeAccountRow(CamelModel):
    """账户配置行（token 只回掩码，明文不出库）。"""

    id: int
    name: str
    counter_account_id: str
    is_agent: bool = False
    is_enabled: bool = True
    token_masked: str = ""
    last_error: str | None = None
    last_synced_at: datetime | None = None
    created_at: datetime | None = None


class PaperTradeAccountListResponse(CamelModel):
    """用户自有账户列表。"""

    items: list[PaperTradeAccountRow] = []


class PaperTradeAccountCreateRequest(CamelModel):
    """新增账户配置（掘金仿真 token + counter account_id）。"""

    name: str
    token: str
    counter_account_id: str


class PaperTradeAccountUpdateRequest(CamelModel):
    """更新账户配置（未提供的字段不变）。"""

    name: str | None = None
    token: str | None = None
    counter_account_id: str | None = None


class PaperTradePlaceOrderRequest(CamelModel):
    """人工下单请求（限价单必须带价格，柜台校验手数整数倍）。"""

    account_id: int
    """平台 6 位股票代码（或带柜台前缀完整代码，服务层按 stock_basic 主数据解析）。"""
    symbol: str
    side: str
    volume: int
    order_type: str = "limit"
    price: float = 0.0


class PaperTradeActionResponse(CamelModel):
    """下单/撤单动作结果。"""

    success: bool = True
    cl_ord_id: str = ""
    message: str = ""


class PaperTradeAccountSyncResponse(CamelModel):
    """单账户即时同步摘要（下单/撤单后调用）。"""

    trade_date: str
    account_id: int
    orders: int = 0
    executions: int = 0
    nav: float | None = None


# ============================================================
# 管理端
# ============================================================


class PaperTradeAdminAccountRow(PaperTradeAccountRow):
    """管理端账户行（附带归属用户）。"""

    user_id: int


class PaperTradeAdminAccountListResponse(CamelModel):
    """管理端全平台账户列表。"""

    items: list[PaperTradeAdminAccountRow] = []
