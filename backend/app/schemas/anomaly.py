"""异动分析（板块 / 个股）API 的 Pydantic schemas。"""

from datetime import date

from app.schemas.base import CamelModel


class SectorAnomalyItem(CamelModel):
    """板块异动条目。"""

    sector_type: str
    sector_code: str
    sector_name: str
    change_pct: float | None = None
    amount: float | None = None
    amount_ratio: float | None = None
    up_count: int | None = None
    down_count: int | None = None
    anomaly_types: list[str] = []
    strength: int
    attribution_category: str | None = None
    attribution_summary: str | None = None


class SectorAnomalyResponse(CamelModel):
    """板块异动榜。"""

    trade_date: date
    total: int = 0
    items: list[SectorAnomalyItem] = []


class StockAnomalyItem(CamelModel):
    """个股异动条目。"""

    stock_code: str
    stock_name: str
    close: float | None = None
    change_pct: float | None = None
    turnover_rate: float | None = None
    volume_ratio: float | None = None
    ma60: float | None = None
    is_above_ma60: bool = False
    ma60_breakout: bool = False
    anomaly_types: list[str] = []
    strength: int
    attribution_category: str | None = None
    attribution_summary: str | None = None
    is_watchlist: bool = False


class StockAnomalyResponse(CamelModel):
    """个股异动榜（命中自选股的条目带关联标注）。"""

    trade_date: date
    total: int = 0
    items: list[StockAnomalyItem] = []


class AnomalyTradeDatesResponse(CamelModel):
    """有异动检测数据的交易日列表（升序），日历打点用。"""

    trade_dates: list[date] = []
