"""多周期复盘窗口模型（B2）：六档周期、本期/上期窗口与交易日对齐。

纯日期算术（``period_bounds`` / ``previous_period_bounds`` / ``map_custom_range``）
不触库，便于单测；``resolve_review_window`` / ``resolve_previous_window`` /
``resolve_custom_window`` 按 ``market_trade_calendar`` 权威日历把窗口收边到交易日，
日历未覆盖时按工作日近似（与 ``trade_calendar_service.is_trading_day`` 兜底口径一致）。

日/周/月窗口语义与原 ``agent_review_service.resolve_window`` 完全一致，新增
季/半年/年三档。窗口只描述复盘内容维度，触发时机由调用方决定
（docs/requirement/09-multi-period-review-requirement.md §4.1/§4.3）。
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_trade_calendar import MarketTradeCalendar

#: 复盘周期（六档；日/周/月为既有能力，季/半年/年为 B2 新增）
ReviewPeriod = Literal["day", "week", "month", "quarter", "half_year", "year"]

#: Literal 运行时不可迭代：白名单单独维护（API 入参 / 注册表校验用）
REVIEW_PERIODS: tuple[ReviewPeriod, ...] = (
    "day",
    "week",
    "month",
    "quarter",
    "half_year",
    "year",
)

#: 长周期：不做全量逐笔（输入筛关键交易）、只沉淀体系级经验（§4.2/§4.6）
LONG_REVIEW_PERIODS: tuple[ReviewPeriod, ...] = ("quarter", "half_year", "year")

_MARKET = "cn"

#: 自定义区间超过 12 个月时的提示（§4.3：> 12 月提示改用年档）
CUSTOM_RANGE_TOO_LONG = "自定义区间跨度超过 12 个月，建议使用年档查看完整年度复盘"


def is_long_period(period: ReviewPeriod) -> bool:
    """是否长周期（季/半年/年）：决定关键交易筛选与经验沉淀口径。"""
    return period in LONG_REVIEW_PERIODS


@dataclass(frozen=True)
class ReviewWindow:
    """已对齐交易日的复盘窗口。

    ``start``/``end`` 为窗口内首个/末个交易日；窗口内无交易日时回退请求区间
    边界并由 ``is_empty`` 标记，调用方决定是否跳过（生成路径不静默改期）。
    """

    period: ReviewPeriod
    requested_start: date
    requested_end: date
    start: date
    end: date
    trading_days: tuple[date, ...]
    warning: str | None = None

    @property
    def is_empty(self) -> bool:
        return not self.trading_days

    @property
    def trading_day_count(self) -> int:
        return len(self.trading_days)

    @property
    def trimmed(self) -> bool:
        """请求区间是否因非交易日被收边（报告需标注实际起止）。"""
        return bool(self.trading_days) and (
            self.start > self.requested_start or self.end < self.requested_end
        )


@dataclass(frozen=True)
class CustomRangeMapping:
    """自定义区间 → 报告框架的映射结果（§4.3）。"""

    period: ReviewPeriod
    span_days: int
    warning: str | None = None


def _add_months(day: date, months: int) -> date:
    """自然月偏移（月末日按目标月天数收敛，如 1/31 + 1 月 = 2/28）。"""
    index = day.month - 1 + months
    year = day.year + index // 12
    month = index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day.day, last_day))


def period_bounds(period: ReviewPeriod, trade_date: date) -> tuple[date, date]:
    """本期窗口（周期首日 → 基准日），未按交易日历收边。"""
    if period == "day":
        return trade_date, trade_date
    if period == "week":
        return trade_date - timedelta(days=trade_date.weekday()), trade_date
    if period == "month":
        return trade_date.replace(day=1), trade_date
    if period == "quarter":
        first_month = (trade_date.month - 1) // 3 * 3 + 1
        return trade_date.replace(month=first_month, day=1), trade_date
    if period == "half_year":
        return trade_date.replace(month=1 if trade_date.month <= 6 else 7, day=1), trade_date
    return trade_date.replace(month=1, day=1), trade_date


def previous_period_bounds(period: ReviewPeriod, trade_date: date) -> tuple[date, date]:
    """上一完整自然周期（未按交易日历收边）。

    ``day`` 返回前一自然日，真实「上一交易日」由 ``resolve_previous_window``
    经日历回退确定（周一的前一日是周日，不能直接当窗口）。
    """
    if period == "day":
        candidate = trade_date - timedelta(days=1)
        return candidate, candidate
    if period == "week":
        monday = trade_date - timedelta(days=trade_date.weekday())
        return monday - timedelta(days=7), monday - timedelta(days=1)
    current_start = period_bounds(period, trade_date)[0]
    previous_end = current_start - timedelta(days=1)
    return period_bounds(period, previous_end)[0], previous_end


def map_custom_range(start: date, end: date) -> CustomRangeMapping:
    """自定义区间映射到最接近的报告框架（§4.3，按自然月跨度左闭右开）。

    跨度 < 1 月→周；1–3 月→月；3–6 月→季；6–12 月→半年；> 12 月→年档并提示。
    """
    if end < start:
        raise ValueError(f"区间结束日 {end.isoformat()} 早于开始日 {start.isoformat()}")
    span_days = (end - start).days + 1
    if end < _add_months(start, 1):
        period: ReviewPeriod = "week"
        warning = None
    elif end < _add_months(start, 3):
        period = "month"
        warning = None
    elif end < _add_months(start, 6):
        period = "quarter"
        warning = None
    elif end <= _add_months(start, 12):
        period = "half_year"
        warning = None
    else:
        period = "year"
        warning = CUSTOM_RANGE_TOO_LONG
    return CustomRangeMapping(period=period, span_days=span_days, warning=warning)


def _weekdays(start: date, end: date) -> list[date]:
    days: list[date] = []
    day = start
    while day <= end:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return days


async def list_trading_days(
    session: AsyncSession, start: date, end: date
) -> list[date]:
    """区间内交易日（升序）。

    日历行权威；整个区间无任何日历行（未覆盖）时按工作日近似，与
    ``trade_calendar_service.is_trading_day`` 的兜底口径一致。区间全部是
    休市日（如春节周）时返回空列表，而非回退工作日。
    """
    if end < start:
        return []
    rows = (
        await session.execute(
            select(
                MarketTradeCalendar.calendar_date, MarketTradeCalendar.is_trading
            )
            .where(
                MarketTradeCalendar.market == _MARKET,
                MarketTradeCalendar.calendar_date.between(start, end),
            )
            .order_by(MarketTradeCalendar.calendar_date)
        )
    ).all()
    if not rows:
        return _weekdays(start, end)
    return [day for day, is_trading in rows if is_trading]


def _build_window(
    period: ReviewPeriod,
    requested_start: date,
    requested_end: date,
    days: list[date],
    warning: str | None = None,
) -> ReviewWindow:
    return ReviewWindow(
        period=period,
        requested_start=requested_start,
        requested_end=requested_end,
        start=days[0] if days else requested_start,
        end=days[-1] if days else requested_end,
        trading_days=tuple(days),
        warning=warning,
    )


async def resolve_review_window(
    session: AsyncSession, period: ReviewPeriod, trade_date: date
) -> ReviewWindow:
    """本期窗口：周期首日 → 基准交易日，收边到区间内实际交易日。"""
    requested_start, requested_end = period_bounds(period, trade_date)
    days = await list_trading_days(session, requested_start, requested_end)
    return _build_window(period, requested_start, requested_end, days)


async def resolve_previous_window(
    session: AsyncSession, period: ReviewPeriod, trade_date: date
) -> ReviewWindow:
    """上一完整周期窗口。

    ``day`` 的「上一交易日」经日历回退确定（周一 → 上周五）；其余周期取上一
    自然周期的起止日后收边到交易日，全部休市时返回空窗口由调用方处理。
    """
    if period == "day":
        # 延迟 import：market 子域聚合面大，避免与 trading 形成顶层环导入
        from app.services.market import trade_calendar_service

        candidate = trade_date - timedelta(days=1)
        previous = await trade_calendar_service.resolve_trade_date_on_or_before(
            session, candidate
        )
        return _build_window(period, candidate, candidate, [previous])

    requested_start, requested_end = previous_period_bounds(period, trade_date)
    days = await list_trading_days(session, requested_start, requested_end)
    return _build_window(period, requested_start, requested_end, days)


async def resolve_custom_window(
    session: AsyncSession, start: date, end: date
) -> ReviewWindow:
    """自定义区间窗口：映射报告框架 + 收边到交易日（§4.3）。"""
    mapping = map_custom_range(start, end)
    days = await list_trading_days(session, start, end)
    return _build_window(
        mapping.period, start, end, days, warning=mapping.warning
    )


async def resolve_explicit_window(
    session: AsyncSession, period: ReviewPeriod, start: date, end: date
) -> ReviewWindow:
    """显式区间窗口：沿用调用方指定的报告框架（上期快捷项 / 带周期的区间选择）。

    与 ``resolve_custom_window`` 的区别只在于周期来源——后者按跨度自动映射
    （§4.3），本函数保留框架，用于「上期」或前端已选定档位的精确窗口。
    """
    days = await list_trading_days(session, start, end)
    return _build_window(period, start, end, days)


async def is_last_trading_day_of_week(session: AsyncSession, day: date) -> bool:
    """day 之后最近的交易日是否已跨入下一周（ISO 周）——周五遇休市时周四即为周期末。"""
    nxt = await _next_trading_day(session, day)
    return nxt is None or nxt.isocalendar()[:2] != day.isocalendar()[:2]


async def is_last_trading_day_of_month(session: AsyncSession, day: date) -> bool:
    """day 之后最近的交易日是否已跨入下一月。"""
    nxt = await _next_trading_day(session, day)
    return nxt is None or (nxt.year, nxt.month) != (day.year, day.month)


async def _next_trading_day(session: AsyncSession, day: date) -> date | None:
    # 延迟 import：market 子域聚合面大，避免与 trading 形成顶层环导入
    from app.services.market.trade_calendar_service import next_trading_day

    return await next_trading_day(session, day)
