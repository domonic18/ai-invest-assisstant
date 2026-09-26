"""交易日历管理 schemas（后台月历视图 + 单日人工覆盖 + 种子刷新）。"""

from datetime import date

from pydantic import BaseModel, Field

from app.schemas.base import CamelModel


class TradeCalendarDayResponse(CamelModel):
    """单日日历行。"""

    calendar_date: date
    is_trading: bool
    source: str
    remark: str | None = None


class TradeCalendarCoverage(CamelModel):
    """年度覆盖元信息：min/max 为 None 表示该年无任何日历行（未覆盖）。"""

    min_date: date | None = None
    max_date: date | None = None
    trading_days: int = 0
    non_trading_days: int = 0


class TradeCalendarYearResponse(CamelModel):
    """年度日历 + 覆盖元信息（月历视图渲染数据源）。"""

    year: int
    days: list[TradeCalendarDayResponse]
    coverage: TradeCalendarCoverage


class TradeCalendarDayUpdate(CamelModel):
    """单日人工覆盖请求。"""

    is_trading: bool
    remark: str | None = Field(default=None, max_length=200)


class TradeCalendarSeedRequest(BaseModel):
    """种子刷新请求：缺省刷新当年 + 下一年。"""

    years: list[int] | None = None


class TradeCalendarSeedResponse(CamelModel):
    """种子刷新结果。"""

    years: list[int]
    written: int
