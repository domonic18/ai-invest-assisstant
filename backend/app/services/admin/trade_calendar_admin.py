"""交易日历后台管理服务：年度月历视图、单日人工覆盖、种子刷新。"""

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import today_cn
from app.repositories.market import trade_calendar_repository
from app.schemas.trade_calendar import (
    TradeCalendarCoverage,
    TradeCalendarDayResponse,
    TradeCalendarYearResponse,
)
from app.services.market.trade_calendar_service import (
    regenerate_from_sina,
    set_day_manual,
)


def _to_day_response(row: object) -> TradeCalendarDayResponse:
    """ORM 行转 wire schema（from_attributes 之外的显式收敛，便于单测桩）。"""
    return TradeCalendarDayResponse(
        calendar_date=row.calendar_date,  # type: ignore[attr-defined]
        is_trading=row.is_trading,  # type: ignore[attr-defined]
        source=row.source,  # type: ignore[attr-defined]
        remark=row.remark,  # type: ignore[attr-defined]
    )


async def get_year(
    session: AsyncSession, year: int | None = None
) -> TradeCalendarYearResponse:
    """查询年度日历与覆盖元信息（year 缺省当年）。"""
    if year is None:
        year = today_cn().year
    rows = await trade_calendar_repository.get_range(
        session, date(year, 1, 1), date(year, 12, 31)
    )
    days = [_to_day_response(row) for row in rows]
    coverage = TradeCalendarCoverage(
        min_date=rows[0].calendar_date if rows else None,
        max_date=rows[-1].calendar_date if rows else None,
        trading_days=sum(1 for d in days if d.is_trading),
        non_trading_days=sum(1 for d in days if not d.is_trading),
    )
    return TradeCalendarYearResponse(
        year=year, days=days, coverage=coverage
    )


async def set_day(
    session: AsyncSession,
    day: date,
    is_trading: bool,
    remark: str | None = None,
) -> TradeCalendarDayResponse:
    """单日人工覆盖（过去日拒绝，守卫在 trade_calendar_service.set_day_manual）。"""
    row = await set_day_manual(session, day, is_trading, remark)
    return _to_day_response(row)


async def seed(
    session: AsyncSession, years: list[int] | None = None
) -> tuple[list[int], int]:
    """新浪日历种子刷新，返回 (生效年份列表, 写入行数)。"""
    if years is None:
        this_year = today_cn().year
        years = [this_year, this_year + 1]
    written = await regenerate_from_sina(session, years)
    return years, written
