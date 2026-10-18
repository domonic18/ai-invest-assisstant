"""行情派发服务（market_dispatch_service）契约测试。"""


from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.collector_log import CollectorLog
from app.schemas.market import CollectTaskResult
from app.services.collector import market_dispatch_service
from app.services.market import (
    market_service,
    trade_calendar_service,
)

_DISPATCH_SVC = "app.services.collector.market_dispatch_service"


@pytest.mark.unit
class TestBackfillTradeDate:
    @pytest.mark.asyncio
    async def test_rejects_non_trading_day(self) -> None:
        session = AsyncMock()
        with (
            patch.object(
                trade_calendar_service.trade_calendar_repository,
                "get_one",
                AsyncMock(return_value=None),
            ),
            pytest.raises(market_service.NonTradingDayError),
        ):
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

        terminal = CollectTaskResult(
            task="kline", status="success", items_collected=41
        )

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
            patch(
                f"{_DISPATCH_SVC}._find_running_kline_log",
                AsyncMock(return_value=None),
            ),
            patch(
                f"{_DISPATCH_SVC}._wait_kline_terminal",
                AsyncMock(return_value=terminal),
            ) as mock_wait,
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
        # 显式日期随派发下发：个股/指数 kline 的交易日预检豁免信号
        assert names[5] == "index-kline"
        assert calls[5][1] == {"end_date": "2026-07-17"}
        assert names[6] == "kline"
        assert calls[6][1] == {
            "symbols": ["000001", "600519"],
            "end_date": "2026-07-17",
        }
        mock_wait.assert_awaited_once_with(7)
        assert results[-1] is terminal

    @pytest.mark.asyncio
    async def test_running_kline_backfill_is_reused(self) -> None:
        """窗口内同标的补采在执行：复用既有任务，不重复派发 kline。"""
        session = AsyncMock()
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
            patch(
                f"{_DISPATCH_SVC}._find_running_kline_log",
                AsyncMock(return_value=MagicMock(id=42)),
            ),
        ):
            results = await market_service.collect_market_data(
                session, date(2026, 7, 17), ["000001"]
            )

        assert "kline" not in [name for name, _ in calls]
        reused = results[-1]
        assert reused.task == "kline"
        assert reused.status == "running"
        assert reused.message is not None and "已复用既有任务" in reused.message

    @pytest.mark.asyncio
    async def test_wait_kline_terminal_maps_terminal_log(self) -> None:
        """终态等待把 collector_log 真实终态映射为结果（含 message/error 兜底）。"""
        log = MagicMock(
            status="success", records_count=41, message=None, error_msg=None
        )
        mock_session = AsyncMock()
        mock_session.get.return_value = log
        factory = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_session),
                __aexit__=AsyncMock(return_value=None),
            )
        )
        with (
            patch(f"{_DISPATCH_SVC}.AsyncSessionLocal", factory),
            patch(f"{_DISPATCH_SVC}.asyncio.sleep", AsyncMock()),
        ):
            result = await market_dispatch_service._wait_kline_terminal(9)

        assert result.task == "kline"
        assert result.status == "success"
        assert result.items_collected == 41
        mock_session.get.assert_awaited_once_with(CollectorLog, 9)

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
        with (
            patch.object(
                trade_calendar_service.trade_calendar_repository,
                "get_one",
                AsyncMock(return_value=None),
            ),
            pytest.raises(market_service.NonTradingDayError),
        ):
            await market_service.collect_market_data(
                session, date(2026, 7, 19), ["000001"]
            )
