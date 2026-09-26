"""交易日历服务单测：DB 日历权威口径 + 无覆盖时的指数日 K 兜底。"""

from contextlib import contextmanager
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.clock import today_cn
from app.core.exceptions import BadRequestError
from app.services.market import market_service, trade_calendar_service
from app.services.market.trade_calendar_service import (
    SCHEDULE_NON_TRADING,
    SCHEDULE_TRADING,
    SCHEDULE_UNKNOWN,
)


@contextmanager
def _no_calendar():
    """模拟日历表无覆盖（回退指数日 K 的历史口径，供既有用例复用）。"""
    with (
        patch.object(
            trade_calendar_service.trade_calendar_repository,
            "get_one",
            AsyncMock(return_value=None),
        ),
        patch.object(
            trade_calendar_service.trade_calendar_repository,
            "get_range",
            AsyncMock(return_value=[]),
        ),
    ):
        yield


def _calendar_row(day: date, is_trading: bool, source: str = "seed") -> MagicMock:
    row = MagicMock()
    row.calendar_date = day
    row.is_trading = is_trading
    row.source = source
    return row


@pytest.mark.unit
class TestResolveTradeDateOnOrBefore:
    @pytest.mark.asyncio
    async def test_returns_kline_max_when_covered(self) -> None:
        with (
            _no_calendar(),
            patch(
                "app.services.market.trade_calendar_service.fetch_max_daily_date_on_or_before",
                AsyncMock(return_value=date(2026, 9, 4)),
            ),
        ):
            result = await trade_calendar_service.resolve_trade_date_on_or_before(
                MagicMock(), date(2026, 9, 5)
            )
        assert result == date(2026, 9, 4)

    @pytest.mark.asyncio
    async def test_weekend_walks_back_to_friday_without_kline(self) -> None:
        with (
            _no_calendar(),
            patch(
                "app.services.market.trade_calendar_service.fetch_max_daily_date_on_or_before",
                AsyncMock(return_value=None),
            ),
        ):
            result = await trade_calendar_service.resolve_trade_date_on_or_before(
                MagicMock(), date(2026, 9, 5)
            )
        assert result == date(2026, 9, 4)

    @pytest.mark.asyncio
    async def test_calendar_authoritative_holiday_walks_back(self) -> None:
        """日历覆盖时节假日归位上一交易日（消除指数日 K 近似）。"""
        rows = [
            _calendar_row(date(2026, 10, 1), False),
            _calendar_row(date(2026, 10, 2), False),
            _calendar_row(date(2026, 9, 30), True),
        ]
        with patch.object(
            trade_calendar_service.trade_calendar_repository,
            "get_range",
            AsyncMock(return_value=rows),
        ) as mock_get_range:
            result = await trade_calendar_service.resolve_trade_date_on_or_before(
                MagicMock(), date(2026, 10, 2)
            )
        assert result == date(2026, 9, 30)
        mock_get_range.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_calendar_gap_falls_back_to_kline(self) -> None:
        """断档（查询日无行）时交由指数日 K 兜底。"""
        rows = [_calendar_row(date(2026, 9, 30), True)]
        with (
            patch.object(
                trade_calendar_service.trade_calendar_repository,
                "get_range",
                AsyncMock(return_value=rows),
            ),
            patch(
                "app.services.market.trade_calendar_service.fetch_max_daily_date_on_or_before",
                AsyncMock(return_value=date(2026, 9, 29)),
            ),
        ):
            result = await trade_calendar_service.resolve_trade_date_on_or_before(
                MagicMock(), date(2026, 10, 2)
            )
        assert result == date(2026, 9, 29)


@pytest.mark.unit
class TestClassifyScheduleDay:
    @pytest.mark.asyncio
    async def test_trading_day(self) -> None:
        with patch.object(
            trade_calendar_service.trade_calendar_repository,
            "get_one",
            AsyncMock(return_value=_calendar_row(today_cn(), True)),
        ):
            assert (
                await trade_calendar_service.classify_schedule_day(
                    MagicMock(), today_cn()
                )
                == SCHEDULE_TRADING
            )

    @pytest.mark.asyncio
    async def test_non_trading_day(self) -> None:
        with patch.object(
            trade_calendar_service.trade_calendar_repository,
            "get_one",
            AsyncMock(return_value=_calendar_row(today_cn(), False)),
        ):
            assert (
                await trade_calendar_service.classify_schedule_day(
                    MagicMock(), today_cn()
                )
                == SCHEDULE_NON_TRADING
            )

    @pytest.mark.asyncio
    async def test_unknown_when_uncovered(self) -> None:
        """无日历行返回 unknown（D5：拒绝调度，不静默回退周末启发）。"""
        with patch.object(
            trade_calendar_service.trade_calendar_repository,
            "get_one",
            AsyncMock(return_value=None),
        ):
            assert (
                await trade_calendar_service.classify_schedule_day(
                    MagicMock(), today_cn()
                )
                == SCHEDULE_UNKNOWN
            )


@pytest.mark.unit
class TestIsTradingDayCalendarAuthoritative:
    @pytest.mark.asyncio
    async def test_calendar_row_wins_over_weekday(self) -> None:
        """调休上班的周六：日历行为权威，不被周末启发覆盖。"""
        saturday = date(2026, 9, 26)
        assert saturday.weekday() == 5
        with patch.object(
            trade_calendar_service.trade_calendar_repository,
            "get_one",
            AsyncMock(return_value=_calendar_row(saturday, True)),
        ):
            assert await market_service.is_trading_day(MagicMock(), saturday) is True

    @pytest.mark.asyncio
    async def test_calendar_row_wins_over_kline_bar(self) -> None:
        """临时休市的工作日：日历 false 直接判定，不查指数日 K。"""
        with (
            patch.object(
                trade_calendar_service.trade_calendar_repository,
                "get_one",
                AsyncMock(return_value=_calendar_row(date(2026, 10, 1), False)),
            ),
            patch.object(
                trade_calendar_service,
                "fetch_max_daily_date",
                AsyncMock(return_value=date(2026, 10, 1)),
            ) as mock_kline,
        ):
            assert (
                await market_service.is_trading_day(MagicMock(), date(2026, 10, 1))
                is False
            )
        mock_kline.assert_not_awaited()


@pytest.mark.unit
class TestSetDayManual:
    @pytest.mark.asyncio
    async def test_past_day_rejected(self) -> None:
        with patch.object(
            trade_calendar_service, "today_cn", lambda: date(2026, 9, 25)
        ):
            with pytest.raises(BadRequestError, match="不可修改历史日期"):
                await trade_calendar_service.set_day_manual(
                    MagicMock(), date(2026, 9, 24), True
                )

    @pytest.mark.asyncio
    async def test_today_allowed_and_commits(self) -> None:
        session = AsyncMock()
        row = _calendar_row(date(2026, 9, 25), False, source="manual")
        with (
            patch.object(
                trade_calendar_service, "today_cn", lambda: date(2026, 9, 25)
            ),
            patch.object(
                trade_calendar_service.trade_calendar_repository,
                "upsert_manual_day",
                AsyncMock(return_value=row),
            ) as mock_upsert,
        ):
            result = await trade_calendar_service.set_day_manual(
                session, date(2026, 9, 25), False, remark="临时休市"
            )
        assert result is row
        mock_upsert.assert_awaited_once_with(
            session, date(2026, 9, 25), False, "临时休市"
        )
        session.commit.assert_awaited_once()


@pytest.mark.unit
class TestRegenerateFromSina:
    @pytest.mark.asyncio
    async def test_generates_full_year_rows_including_weekends(self) -> None:
        """种子行覆盖整年（含周末非交易日），周末不被误标交易日。"""
        session = AsyncMock()
        trading = {
            date(2026, 1, 1),
            date(2026, 1, 2),
        }  # 其余全年均非交易日（简化样本）
        with (
            patch.object(
                trade_calendar_service,
                "_fetch_sina_trade_dates",
                AsyncMock(return_value=trading),
            ),
            patch.object(
                trade_calendar_service.trade_calendar_repository,
                "upsert_seed_rows",
                AsyncMock(return_value=365),
            ) as mock_upsert,
        ):
            written = await trade_calendar_service.regenerate_from_sina(
                session, [2026]
            )
        assert written == 365
        rows = mock_upsert.await_args.args[1]
        assert len(rows) == 365
        by_date = {r["calendar_date"]: r["is_trading"] for r in rows}
        assert by_date[date(2026, 1, 1)] is True
        assert by_date[date(2026, 1, 3)] is False  # 周六
        assert by_date[date(2026, 1, 4)] is False  # 周日
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_default_years_are_current_and_next(self) -> None:
        session = AsyncMock()
        with (
            patch.object(
                trade_calendar_service, "today_cn", lambda: date(2026, 9, 25)
            ),
            patch.object(
                trade_calendar_service,
                "_fetch_sina_trade_dates",
                AsyncMock(return_value=set()),
            ),
            patch.object(
                trade_calendar_service.trade_calendar_repository,
                "upsert_seed_rows",
                AsyncMock(return_value=0),
            ) as mock_upsert,
        ):
            await trade_calendar_service.regenerate_from_sina(session)
        rows = mock_upsert.await_args.args[1]
        dates = [r["calendar_date"] for r in rows]
        assert min(dates) == date(2026, 1, 1)
        assert max(dates) == date(2027, 12, 31)
        assert len(rows) == 730

    @pytest.mark.asyncio
    async def test_sina_empty_raises(self) -> None:
        with patch.object(
            trade_calendar_service,
            "_fetch_sina_trade_dates",
            AsyncMock(side_effect=BadRequestError("新浪交易日历返回为空")),
        ):
            with pytest.raises(BadRequestError):
                await trade_calendar_service.regenerate_from_sina(
                    AsyncMock(), [2026]
                )


@pytest.mark.unit
class TestResolveLatestTradeDate:
    @pytest.mark.asyncio
    async def test_returns_today_when_no_kline(self) -> None:
        session = AsyncMock()
        with (
            _no_calendar(),
            patch.object(
                trade_calendar_service, "fetch_max_daily_date", AsyncMock(return_value=None)
            ),
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
        with (
            _no_calendar(),
            patch.object(
                trade_calendar_service,
                "fetch_max_daily_date",
                AsyncMock(return_value=kline_max),
            ),
        ):
            result = await market_service.resolve_latest_trade_date(session)
        expected = today if today.weekday() < 5 else kline_max
        assert result == expected

    @pytest.mark.asyncio
    async def test_falls_back_to_kline_max_without_breadth(self) -> None:
        session = AsyncMock()
        session.scalar.return_value = 0
        kline_max = date(2026, 7, 17)
        with (
            _no_calendar(),
            patch.object(
                trade_calendar_service,
                "fetch_max_daily_date",
                AsyncMock(return_value=kline_max),
            ),
        ):
            assert await market_service.resolve_latest_trade_date(session) == (
                kline_max
            )


@pytest.mark.unit
class TestIsTradingDay:
    @pytest.mark.asyncio
    async def test_weekend_is_not_trading_day(self) -> None:
        session = AsyncMock()
        with _no_calendar():
            assert await market_service.is_trading_day(
                session, date(2026, 7, 19)
            ) is False  # 周日

    @pytest.mark.asyncio
    async def test_past_day_with_kline_bar(self) -> None:
        session = AsyncMock()
        with (
            _no_calendar(),
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
            _no_calendar(),
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
        with (
            _no_calendar(),
            patch.object(
                trade_calendar_service,
                "fetch_max_daily_date",
                AsyncMock(return_value=date(2026, 7, 17)),
            ),
        ):
            assert await market_service.is_trading_day(
                session, date(2026, 7, 20)
            ) is True


@pytest.mark.unit
class TestResolveDefaultViewDate:
    """复盘视图缺省日：交易日（按放行口径）取当天，非交易日回退最近交易日。"""

    @pytest.mark.asyncio
    async def test_weekday_before_kline_returns_today(self) -> None:
        """盘前（日 K 尚无当日行）工作日：取当天，让未就绪区块呈空态。"""
        session = AsyncMock()
        with (
            _no_calendar(),
            patch.object(
                trade_calendar_service, "today_cn", lambda: date(2026, 7, 17)
            ),
            patch.object(
                trade_calendar_service,
                "fetch_max_daily_date",
                AsyncMock(return_value=date(2026, 7, 16)),
            ),
        ):
            assert await trade_calendar_service.resolve_default_view_date(session) == (
                date(2026, 7, 17)
            )

    @pytest.mark.asyncio
    async def test_weekend_falls_back_to_latest_trade_date(self) -> None:
        session = AsyncMock()
        with (
            _no_calendar(),
            patch.object(
                trade_calendar_service, "today_cn", lambda: date(2026, 7, 18)
            ),
            patch.object(
                trade_calendar_service,
                "fetch_max_daily_date_on_or_before",
                AsyncMock(return_value=date(2026, 7, 17)),
            ),
        ):
            assert await trade_calendar_service.resolve_default_view_date(session) == (
                date(2026, 7, 17)
            )

    @pytest.mark.asyncio
    async def test_today_with_kline_bar_returns_today(self) -> None:
        """收盘后日 K 已入库：has_daily_bar 命中，仍取当天。"""
        session = AsyncMock()
        with (
            _no_calendar(),
            patch.object(
                trade_calendar_service, "today_cn", lambda: date(2026, 7, 17)
            ),
            patch.object(
                trade_calendar_service,
                "fetch_max_daily_date",
                AsyncMock(return_value=date(2026, 7, 17)),
            ),
            patch.object(
                trade_calendar_service, "has_daily_bar", AsyncMock(return_value=True)
            ),
        ):
            assert await trade_calendar_service.resolve_default_view_date(session) == (
                date(2026, 7, 17)
            )
