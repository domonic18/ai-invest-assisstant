"""模拟盘盘后同步采集器契约测试（交易日/未配置/锁冲突/SUCCESS 映射）。"""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import ConflictError
from app.services.trading.errors import (
    PaperTradeGatewayError,
    PaperTradeNotConfiguredError,
)
from collector.core.base import CollectStatus
from collector.spiders.paper_trade_sync import PaperTradeSyncCollector

_TRADE_DATE = date(2026, 9, 24)


def _collector() -> PaperTradeSyncCollector:
    return PaperTradeSyncCollector(
        {"source": "internal", "data_type": "paper-trade-sync"}
    )


def _patches(
    trading_day: bool, sync_side_effect=None, sync_return=None
):
    return (
        patch(
            "collector.spiders.paper_trade_sync.is_trading_day",
            return_value=trading_day,
        ),
        patch(
            "collector.spiders.paper_trade_sync.latest_trading_day",
            return_value=_TRADE_DATE,
        ),
        patch(
            "collector.spiders.paper_trade_sync.paper_trade_service.sync_daily",
            AsyncMock(return_value=sync_return, side_effect=sync_side_effect),
        ),
    )


_SUMMARY = {
    "trade_date": _TRADE_DATE.isoformat(),
    "orders": 2,
    "executions": 1,
    "nav": 100000.0,
}


@pytest.mark.unit
class TestPaperTradeSyncCollector:
    @pytest.mark.asyncio
    async def test_skips_non_trading_day(self) -> None:
        trading_day, latest, _ = _patches(False)
        with trading_day, latest:
            result = await _collector().run()

        assert result.status == CollectStatus.SKIPPED
        assert "不是交易日" in (result.message or "")

    @pytest.mark.asyncio
    async def test_skips_when_not_configured(self) -> None:
        trading_day, latest, sync = _patches(
            True, sync_side_effect=PaperTradeNotConfiguredError()
        )
        with trading_day, latest, sync:
            result = await _collector().run()

        assert result.status == CollectStatus.SKIPPED
        assert "paper_trade_url 未配置" in (result.message or "")

    @pytest.mark.asyncio
    async def test_skips_when_lock_held(self) -> None:
        trading_day, latest, sync = _patches(
            True, sync_side_effect=ConflictError("模拟盘盘后同步正在执行")
        )
        with trading_day, latest, sync:
            result = await _collector().run()

        assert result.status == CollectStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_success_maps_summary(self) -> None:
        trading_day, latest, sync = _patches(True, sync_return=_SUMMARY)
        with trading_day, latest, sync:
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        assert result.items_stored == 3
        assert result.metadata["trade_date"] == _TRADE_DATE.isoformat()
        assert result.metadata["orders"] == 2

    @pytest.mark.asyncio
    async def test_gateway_error_maps_to_failed(self) -> None:
        trading_day, latest, sync = _patches(
            True, sync_side_effect=PaperTradeGatewayError("柜台错误")
        )
        with trading_day, latest, sync:
            result = await _collector().run()

        assert result.status == CollectStatus.FAILED
        assert result.errors == ["柜台错误"]
