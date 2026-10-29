"""多周期复盘窗口模型契约测试（六档周期 / 上期 / 自定义区间 / 交易日对齐）。"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.trading import agent_review_periods as periods
from app.services.trading.agent_review_periods import (
    CUSTOM_RANGE_TOO_LONG,
    list_trading_days,
    map_custom_range,
    period_bounds,
    previous_period_bounds,
    resolve_custom_window,
    resolve_previous_window,
    resolve_review_window,
)

_TRADE_DATE = date(2026, 7, 15)  # Wednesday


@pytest.mark.unit
class TestPeriodBounds:
    """§4.1 本期窗口：周期首日 → 基准日。"""

    def test_day(self) -> None:
        assert period_bounds("day", _TRADE_DATE) == (_TRADE_DATE, _TRADE_DATE)

    def test_week_anchors_monday(self) -> None:
        assert period_bounds("week", _TRADE_DATE) == (date(2026, 7, 13), _TRADE_DATE)

    def test_month_starts_day_one(self) -> None:
        assert period_bounds("month", _TRADE_DATE) == (date(2026, 7, 1), _TRADE_DATE)

    def test_quarter_starts_quarter_first_day(self) -> None:
        assert period_bounds("quarter", _TRADE_DATE) == (date(2026, 7, 1), _TRADE_DATE)
        assert period_bounds("quarter", date(2026, 2, 10)) == (
            date(2026, 1, 1),
            date(2026, 2, 10),
        )

    def test_half_year_starts_jan_or_jul(self) -> None:
        assert period_bounds("half_year", _TRADE_DATE) == (
            date(2026, 7, 1),
            _TRADE_DATE,
        )
        assert period_bounds("half_year", date(2026, 6, 30)) == (
            date(2026, 1, 1),
            date(2026, 6, 30),
        )

    def test_year_starts_jan_1(self) -> None:
        assert period_bounds("year", _TRADE_DATE) == (date(2026, 1, 1), _TRADE_DATE)


@pytest.mark.unit
class TestPreviousPeriodBounds:
    """§4.1 上期窗口：紧邻的上一完整自然周期。"""

    def test_day_is_previous_calendar_day(self) -> None:
        assert previous_period_bounds("day", _TRADE_DATE) == (
            date(2026, 7, 14),
            date(2026, 7, 14),
        )

    def test_previous_week_is_previous_iso_week(self) -> None:
        assert previous_period_bounds("week", _TRADE_DATE) == (
            date(2026, 7, 6),
            date(2026, 7, 12),
        )

    def test_previous_month(self) -> None:
        assert previous_period_bounds("month", _TRADE_DATE) == (
            date(2026, 6, 1),
            date(2026, 6, 30),
        )
        assert previous_period_bounds("month", date(2026, 1, 5)) == (
            date(2025, 12, 1),
            date(2025, 12, 31),
        )

    def test_previous_quarter(self) -> None:
        assert previous_period_bounds("quarter", _TRADE_DATE) == (
            date(2026, 4, 1),
            date(2026, 6, 30),
        )
        assert previous_period_bounds("quarter", date(2026, 2, 10)) == (
            date(2025, 10, 1),
            date(2025, 12, 31),
        )

    def test_previous_half_year(self) -> None:
        assert previous_period_bounds("half_year", _TRADE_DATE) == (
            date(2026, 1, 1),
            date(2026, 6, 30),
        )
        assert previous_period_bounds("half_year", date(2026, 2, 10)) == (
            date(2025, 7, 1),
            date(2025, 12, 31),
        )

    def test_previous_year(self) -> None:
        assert previous_period_bounds("year", _TRADE_DATE) == (
            date(2025, 1, 1),
            date(2025, 12, 31),
        )


@pytest.mark.unit
class TestMapCustomRange:
    """§4.3 自定义区间 → 报告框架（自然月跨度，左闭右开）。"""

    def test_short_range_uses_week_framework(self) -> None:
        mapping = map_custom_range(date(2026, 9, 1), date(2026, 9, 20))
        assert mapping.period == "week"
        assert mapping.span_days == 20
        assert mapping.warning is None

    def test_one_to_three_months_uses_month_framework(self) -> None:
        assert map_custom_range(date(2026, 9, 1), date(2026, 10, 1)).period == "month"
        assert map_custom_range(date(2026, 9, 1), date(2026, 11, 30)).period == "month"

    def test_three_to_six_months_uses_quarter_framework(self) -> None:
        assert map_custom_range(date(2026, 9, 1), date(2026, 12, 1)).period == "quarter"
        assert map_custom_range(date(2026, 9, 1), date(2027, 2, 28)).period == "quarter"

    def test_six_to_twelve_months_uses_half_year_framework(self) -> None:
        assert map_custom_range(date(2026, 9, 1), date(2027, 3, 1)).period == "half_year"
        assert map_custom_range(date(2026, 9, 1), date(2027, 9, 1)).period == "half_year"

    def test_longer_than_year_uses_year_with_warning(self) -> None:
        mapping = map_custom_range(date(2026, 9, 1), date(2027, 9, 2))
        assert mapping.period == "year"
        assert mapping.warning == CUSTOM_RANGE_TOO_LONG

    def test_month_end_day_is_clamped(self) -> None:
        # 1/31 + 1 月 = 2/28（非闰年），恰好一个月仍归月框架
        assert map_custom_range(date(2026, 1, 31), date(2026, 2, 28)).period == "month"

    def test_rejects_reversed_range(self) -> None:
        with pytest.raises(ValueError, match="早于"):
            map_custom_range(date(2026, 9, 2), date(2026, 9, 1))


def _session_returning(rows: list[tuple[date, bool]]) -> AsyncMock:
    """构造 execute(...).all() 返回指定行的会话替身（all 为同步方法）。"""
    result = MagicMock()
    result.all.return_value = rows
    session = AsyncMock()
    session.execute.return_value = result
    return session


@pytest.mark.unit
class TestListTradingDays:
    @pytest.mark.asyncio
    async def test_uses_calendar_rows(self) -> None:
        session = _session_returning(
            [
                (date(2026, 7, 13), True),
                (date(2026, 7, 14), False),
                (date(2026, 7, 15), True),
            ]
        )
        days = await list_trading_days(session, date(2026, 7, 13), date(2026, 7, 15))
        assert days == [date(2026, 7, 13), date(2026, 7, 15)]

    @pytest.mark.asyncio
    async def test_falls_back_to_weekdays_when_calendar_uncovered(self) -> None:
        session = _session_returning([])
        days = await list_trading_days(session, date(2026, 7, 18), date(2026, 7, 20))
        assert days == [date(2026, 7, 20)]

    @pytest.mark.asyncio
    async def test_holiday_week_stays_empty_without_fallback(self) -> None:
        """日历覆盖且整周休市（如春节周）：返回空窗口，不按工作日放行。"""
        session = _session_returning(
            [
                (date(2026, 10, 5), False),
                (date(2026, 10, 6), False),
            ]
        )
        days = await list_trading_days(session, date(2026, 10, 5), date(2026, 10, 6))
        assert days == []


@pytest.mark.unit
class TestResolveReviewWindow:
    @pytest.mark.asyncio
    async def test_quarter_window_trims_to_trading_days(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def fake_days(session, start, end):  # type: ignore[no-untyped-def]
            return [date(2026, 7, 1), date(2026, 7, 14), date(2026, 7, 15)]

        monkeypatch.setattr(periods, "list_trading_days", fake_days)
        window = await resolve_review_window(AsyncMock(), "quarter", _TRADE_DATE)

        assert window.requested_start == date(2026, 7, 1)
        assert window.start == date(2026, 7, 1)
        assert window.end == _TRADE_DATE
        assert window.trading_day_count == 3
        assert window.trimmed is False

    @pytest.mark.asyncio
    async def test_month_window_marks_trimmed_when_start_is_weekend(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def fake_days(session, start, end):  # type: ignore[no-untyped-def]
            return [date(2026, 8, 3), date(2026, 8, 10)]

        monkeypatch.setattr(periods, "list_trading_days", fake_days)
        window = await resolve_review_window(AsyncMock(), "month", date(2026, 8, 10))

        assert window.requested_start == date(2026, 8, 1)
        assert window.start == date(2026, 8, 3)
        assert window.trimmed is True


@pytest.mark.unit
class TestResolvePreviousWindow:
    @pytest.mark.asyncio
    async def test_day_uses_previous_trading_day_across_weekend(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """周一的前一自然日是周日：必须回退到上周五。"""
        from app.services.market import trade_calendar_service

        async def fake_previous(session, day):  # type: ignore[no-untyped-def]
            return date(2026, 7, 17)

        monkeypatch.setattr(
            trade_calendar_service, "resolve_trade_date_on_or_before", fake_previous
        )
        window = await resolve_previous_window(
            AsyncMock(), "day", date(2026, 7, 20)
        )

        assert (window.start, window.end) == (date(2026, 7, 17), date(2026, 7, 17))

    @pytest.mark.asyncio
    async def test_previous_quarter_trims_to_its_trading_days(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def fake_days(session, start, end):  # type: ignore[no-untyped-def]
            return [date(2026, 4, 1), date(2026, 6, 30)]

        monkeypatch.setattr(periods, "list_trading_days", fake_days)
        window = await resolve_previous_window(AsyncMock(), "quarter", _TRADE_DATE)

        assert window.requested_start == date(2026, 4, 1)
        assert window.requested_end == date(2026, 6, 30)
        assert window.trading_day_count == 2

    @pytest.mark.asyncio
    async def test_empty_holiday_period_is_marked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def fake_days(session, start, end):  # type: ignore[no-untyped-def]
            return []

        monkeypatch.setattr(periods, "list_trading_days", fake_days)
        window = await resolve_previous_window(AsyncMock(), "week", _TRADE_DATE)

        assert window.is_empty is True
        assert window.start == window.requested_start
        assert window.end == window.requested_end


@pytest.mark.unit
class TestResolveCustomWindow:
    @pytest.mark.asyncio
    async def test_maps_framework_and_aligned_bounds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def fake_days(session, start, end):  # type: ignore[no-untyped-def]
            return [date(2026, 9, 1), date(2026, 10, 19), date(2026, 10, 20)]

        monkeypatch.setattr(periods, "list_trading_days", fake_days)
        window = await resolve_custom_window(
            AsyncMock(), date(2026, 9, 1), date(2026, 10, 20)
        )

        assert window.period == "month"
        assert window.start == date(2026, 9, 1)
        assert window.end == date(2026, 10, 20)
        assert window.trading_day_count == 3
        assert window.warning is None

    @pytest.mark.asyncio
    async def test_over_year_range_carries_warning(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def fake_days(session, start, end):  # type: ignore[no-untyped-def]
            return [date(2025, 9, 1), date(2026, 9, 2)]

        monkeypatch.setattr(periods, "list_trading_days", fake_days)
        window = await resolve_custom_window(
            AsyncMock(), date(2025, 9, 1), date(2026, 9, 2)
        )

        assert window.period == "year"
        assert window.warning == CUSTOM_RANGE_TOO_LONG


@pytest.mark.unit
class TestResolveExplicitWindow:
    """显式区间：沿用调用方周期框架（上期/带档位的区间选择），不按跨度映射。"""

    @pytest.mark.asyncio
    async def test_keeps_requested_framework(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def fake_days(session, start, end):  # type: ignore[no-untyped-def]
            return [date(2026, 6, 1), date(2026, 6, 30)]

        monkeypatch.setattr(periods, "list_trading_days", fake_days)
        window = await periods.resolve_explicit_window(
            AsyncMock(), "week", date(2026, 6, 1), date(2026, 6, 30)
        )

        # 跨度两个月本会映射到 month，显式框架须保留 week
        assert window.period == "week"
        assert window.start == date(2026, 6, 1)
        assert window.end == date(2026, 6, 30)
        assert window.warning is None

    @pytest.mark.asyncio
    async def test_empty_range_returns_empty_window(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def fake_days(session, start, end):  # type: ignore[no-untyped-def]
            return []

        monkeypatch.setattr(periods, "list_trading_days", fake_days)
        window = await periods.resolve_explicit_window(
            AsyncMock(), "month", date(2026, 10, 5), date(2026, 10, 7)
        )

        assert window.is_empty is True
        assert (window.start, window.end) == (date(2026, 10, 5), date(2026, 10, 7))
