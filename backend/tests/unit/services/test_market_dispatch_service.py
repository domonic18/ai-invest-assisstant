"""行情派发服务（market_dispatch_service）契约测试。"""


from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.market import (
    market_service,
    trade_calendar_service,
)


@pytest.mark.unit
class TestBackfillTradeDate:
    @pytest.mark.asyncio
    async def test_rejects_non_trading_day(self) -> None:
        session = AsyncMock()
        with pytest.raises(market_service.NonTradingDayError):
            await market_service.backfill_trade_date(session, date(2026, 7, 19))

    @pytest.mark.asyncio
    async def test_dispatches_backfill_tasks_in_order(self) -> None:
        session = AsyncMock()
        day = date(2026, 7, 17)
        calls: list[tuple[str, dict]] = []

        async def fake_dispatch(
            session: object, task_name: str, params: dict, **kwargs: object
        ) -> MagicMock:
            calls.append((task_name, params))
            return MagicMock(id=len(calls))

        with (
            patch.object(
                trade_calendar_service,
                "is_trading_day",
                AsyncMock(return_value=True),
            ),
            patch(
                "collector.runtime.dispatcher.dispatch_collector_task",
                side_effect=fake_dispatch,
            ),
        ):
            results = await market_service.backfill_trade_date(session, day)

        expected = [
            "limit-up-pool",
            "broken-pool",
            "limit-down-pool",
            "market-amount",
            "sector-fund-flow",
        ]
        assert [name for name, _ in calls] == expected
        assert all(p["trade_date"] == "2026-07-17" for _, p in calls)
        assert [r.task for r in results] == expected
        assert all(r.status == "dispatched" for r in results)


@pytest.mark.unit
class TestCollectMarketData:
    @pytest.mark.asyncio
    async def test_dispatches_backfill_index_kline_and_symbols(self) -> None:
        session = AsyncMock()
        day = date(2026, 7, 17)
        calls: list[tuple[str, dict]] = []

        async def fake_dispatch(
            session: object, task_name: str, params: dict, **kwargs: object
        ) -> MagicMock:
            calls.append((task_name, params))
            return MagicMock(id=len(calls))

        with (
            patch.object(
                trade_calendar_service,
                "is_trading_day",
                AsyncMock(return_value=True),
            ),
            patch(
                "collector.runtime.dispatcher.dispatch_collector_task",
                side_effect=fake_dispatch,
            ),
        ):
            results = await market_service.collect_market_data(
                session, day, ["000001", "600519"]
            )

        names = [name for name, _ in calls]
        assert names[:5] == [
            "limit-up-pool",
            "broken-pool",
            "limit-down-pool",
            "market-amount",
            "sector-fund-flow",
        ]
        assert names[5] == "index-kline"
        assert calls[5][1] == {}
        assert names[6] == "kline"
        assert calls[6][1] == {"symbols": ["000001", "600519"]}
        assert [r.task for r in results] == names

    @pytest.mark.asyncio
    async def test_without_symbols_skips_stock_kline_task(self) -> None:
        session = AsyncMock()
        calls: list[str] = []

        async def fake_dispatch(
            session: object, task_name: str, params: dict, **kwargs: object
        ) -> MagicMock:
            calls.append(task_name)
            return MagicMock(id=len(calls))

        with (
            patch.object(
                trade_calendar_service,
                "is_trading_day",
                AsyncMock(return_value=True),
            ),
            patch(
                "collector.runtime.dispatcher.dispatch_collector_task",
                side_effect=fake_dispatch,
            ),
        ):
            results = await market_service.collect_market_data(
                session, date(2026, 7, 17)
            )

        assert calls[-1] == "index-kline"
        assert "kline" not in calls
        assert len(results) == 6

    @pytest.mark.asyncio
    async def test_rejects_non_trading_day(self) -> None:
        session = AsyncMock()
        with pytest.raises(market_service.NonTradingDayError):
            await market_service.collect_market_data(
                session, date(2026, 7, 19), ["000001"]
            )
