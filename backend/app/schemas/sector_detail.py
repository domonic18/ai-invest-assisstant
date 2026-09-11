"""板块详情（真实 K 线 + 资金流 + 异动日）API 的 Pydantic schemas。"""

from datetime import date

from app.schemas.base import CamelModel


class SectorKlineBar(CamelModel):
    """板块指数日 K 单根（同花顺真实 OHLC）。"""

    trade_date: date
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float
    volume: int | None = None
    amount: float | None = None
    change_pct: float | None = None


class SectorFundFlowPoint(CamelModel):
    """板块资金流向单日点（各档单型净额，堆叠柱数据源）。"""

    trade_date: date
    main_net_inflow: float | None = None
    super_large_net: float | None = None
    large_net: float | None = None
    medium_net: float | None = None
    small_net: float | None = None


class SectorAnomalyDay(CamelModel):
    """该板块的异动日记录（走势图标注数据源）。"""

    trade_date: date
    anomaly_types: list[str] = []
    strength: int
    attribution_category: str | None = None
    attribution_summary: str | None = None


class SectorSnapshot(CamelModel):
    """最新板块收盘快照（东财 clist，含成交额/换手/涨跌家数）。"""

    trade_date: date
    close: float | None = None
    change_pct: float | None = None
    amount: float | None = None
    turnover_rate: float | None = None
    up_count: int | None = None
    down_count: int | None = None
    leader_stock_name: str | None = None


class SectorDetailResponse(CamelModel):
    """板块详情聚合（K 线为同花顺真实 OHLC 指数，按板块名桥接）。"""

    sector_type: str
    sector_code: str
    sector_name: str
    bars: list[SectorKlineBar] = []
    fund_flow: list[SectorFundFlowPoint] = []
    anomaly_days: list[SectorAnomalyDay] = []
    snapshot: SectorSnapshot | None = None
