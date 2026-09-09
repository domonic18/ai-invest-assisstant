"""交易日历服务单测（归位查询：≤ 某日的最近交易日）。"""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.clock import today_cn
from app.services.market import market_service, trade_calendar_service


@pytest.mark.unit
class TestResolveTradeDateOnOrBefore:
    @pytest.mark.asyncio
    async def test_returns_kline_max_when_covered(self) -> None:
        with patch(
            "app.services.market.trade_calendar_service.fetch_max_daily_date_on_or_before",
            AsyncMock(return_value=date(2026, 9, 4)),
        ):
            result = await trade_calendar_service.resolve_trade_date_on_or_before(
                MagicMock(), date(2026, 9, 5)
            )
        assert result == date(2026, 9, 4)

    @pytest.mark.asyncio
    async def test_weekend_walks_back_to_friday_without_kline(self) -> None:
        with patch(
            "app.services.market.trade_calendar_service.fetch_max_daily_date_on_or_before",
            AsyncMock(return_value=None),
        ):
            result = await trade_calendar_service.resolve_trade_date_on_or_before(
                MagicMock(), date(2026, 9, 5)
            )
        assert result == date(2026, 9, 4)



@pytest.mark.unit
class TestResolveLatestTradeDate:
    @pytest.mark.asyncio
    async def test_returns_today_when_no_kline(self) -> None:
        session = AsyncMock()
        with patch.object(
            trade_calendar_service, "fetch_max_daily_date", AsyncMock(return_value=None)
        ):
            assert await market_service.resolve_latest_trade_date(session) == (
                today_cn()
            )

    @pytest.mark.asyncio
    async def test_intraday_returns_today_when_breadth_exists(self) -> None:
        session = AsyncMock()
        session.scalar.return_value = 1  # 当日已有涨跌统计
        today = today_cn()
        kline_max = today - timedelta(days=3)
        with patch.object(
            trade_calendar_service,
            "fetch_max_daily_date",
            AsyncMock(return_value=kline_max),
        ):
            result = await market_service.resolve_latest_trade_date(session)
        expected = today if today.weekday() < 5 else kline_max
        assert result == expected

    @pytest.mark.asyncio
    async def test_falls_back_to_kline_max_without_breadth(self) -> None:
        session = AsyncMock()
        session.scalar.return_value = 0
        kline_max = date(2026, 7, 17)
        with patch.object(
            trade_calendar_service,
            "fetch_max_daily_date",
            AsyncMock(return_value=kline_max),
        ):
            assert await market_service.resolve_latest_trade_date(session) == (
                kline_max
            )


@pytest.mark.unit
class TestIsTradingDay:
    @pytest.mark.asyncio
    async def test_weekend_is_not_trading_day(self) -> None:
        session = AsyncMock()
        assert await market_service.is_trading_day(
            session, date(2026, 7, 19)
        ) is False  # 周日

    @pytest.mark.asyncio
    async def test_past_day_with_kline_bar(self) -> None:
        session = AsyncMock()
        with (
            patch.object(
                trade_calendar_service,
                "fetch_max_daily_date",
                AsyncMock(return_value=date(2026, 7, 17)),
            ),
            patch.object(
                trade_calendar_service, "has_daily_bar", AsyncMock(return_value=True)
            ),
        ):
            assert await market_service.is_trading_day(
                session, date(2026, 7, 17)
            ) is True

    @pytest.mark.asyncio
    async def test_past_day_without_kline_bar_is_holiday(self) -> None:
        session = AsyncMock()
        with (
            patch.object(
                trade_calendar_service,
                "fetch_max_daily_date",
                AsyncMock(return_value=date(2026, 7, 17)),
            ),
            patch.object(
                trade_calendar_service, "has_daily_bar", AsyncMock(return_value=False)
            ),
        ):
            assert await market_service.is_trading_day(
                session, date(2026, 7, 16)
            ) is False

    @pytest.mark.asyncio
    async def test_future_weekday_after_kline_max_allowed(self) -> None:
        session = AsyncMock()
        with patch.object(
            trade_calendar_service,
            "fetch_max_daily_date",
            AsyncMock(return_value=date(2026, 7, 17)),
        ):
            assert await market_service.is_trading_day(
                session, date(2026, 7, 20)
            ) is True
