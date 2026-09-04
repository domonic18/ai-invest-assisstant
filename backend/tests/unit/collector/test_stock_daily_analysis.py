"""个股每日 AI 分析采集器契约测试（跳过/单股隔离/全未就绪重试）。"""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.review import ReviewInputDataNotReadyError
from collector.core.base import CollectStatus
from collector.spiders.stock_daily_analysis import StockDailyAnalysisCollector

_TRADE_DATE = date(2026, 9, 1)


def _collector() -> StockDailyAnalysisCollector:
    return StockDailyAnalysisCollector(
        {"source": "internal", "data_type": "ai_stock_daily_analysis"}
    )


def _session_factory() -> tuple[MagicMock, AsyncMock]:
    factory = MagicMock()
    session = AsyncMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory, session


def _patch_calendar(trading: bool = True):
    return (
        patch(
            "collector.spiders.stock_daily_analysis.is_trading_day",
            return_value=trading,
        ),
        patch(
            "collector.spiders.stock_daily_analysis.latest_trading_day",
            return_value=_TRADE_DATE,
        ),
    )


def _analysis(cached: bool) -> SimpleNamespace:
    return SimpleNamespace(cached=cached)


@pytest.mark.unit
class TestStockDailyAnalysisCollector:
    @pytest.mark.asyncio
    async def test_skips_non_trading_day(self) -> None:
        trading_patch, latest_patch = _patch_calendar(trading=False)
        with trading_patch, latest_patch:
            result = await _collector().run()

        assert result.status == CollectStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_skips_when_no_active_watch_stocks(self) -> None:
        factory, _ = _session_factory()
        trading_patch, latest_patch = _patch_calendar()
        with (
            trading_patch,
            latest_patch,
            patch(
                "collector.spiders.stock_daily_analysis.AsyncSessionLocal", factory
            ),
            patch(
                "collector.spiders.stock_daily_analysis.stock_daily_analysis_service"
                ".list_active_watch_stock_codes",
                AsyncMock(return_value=[]),
            ),
        ):
            result = await _collector().run()

        assert result.status == CollectStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_success_mixed_with_single_stock_not_ready(self) -> None:
        """单股未就绪只记录并继续，不阻断整体任务。"""
        factory, _ = _session_factory()

        async def _generate(_session, code, *, trade_date, regenerate=False):
            if code == "600519":
                raise ReviewInputDataNotReadyError()
            return _analysis(cached=False)

        trading_patch, latest_patch = _patch_calendar()
        with (
            trading_patch,
            latest_patch,
            patch(
                "collector.spiders.stock_daily_analysis.AsyncSessionLocal", factory
            ),
            patch(
                "collector.spiders.stock_daily_analysis.stock_daily_analysis_service"
                ".list_active_watch_stock_codes",
                AsyncMock(return_value=["600519", "000001"]),
            ),
            patch(
                "collector.spiders.stock_daily_analysis.stock_daily_analysis_service"
                ".generate_stock_analysis",
                AsyncMock(side_effect=_generate),
            ),
        ):
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        assert result.items_stored == 1
        assert result.metadata["stocks"]["600519"] == "not_ready"
        assert result.metadata["stocks"]["000001"] == "generated"
        assert result.metadata["not_ready"] == 1

    @pytest.mark.asyncio
    async def test_reraises_when_all_stocks_not_ready(self) -> None:
        """全部股票未就绪时异常向上传播，由 Celery 任务重试。"""
        factory, _ = _session_factory()
        trading_patch, latest_patch = _patch_calendar()
        with (
            trading_patch,
            latest_patch,
            patch(
                "collector.spiders.stock_daily_analysis.AsyncSessionLocal", factory
            ),
            patch(
                "collector.spiders.stock_daily_analysis.stock_daily_analysis_service"
                ".list_active_watch_stock_codes",
                AsyncMock(return_value=["600519", "000001"]),
            ),
            patch(
                "collector.spiders.stock_daily_analysis.stock_daily_analysis_service"
                ".generate_stock_analysis",
                AsyncMock(side_effect=ReviewInputDataNotReadyError()),
            ),
            pytest.raises(ReviewInputDataNotReadyError),
        ):
            await _collector().run()

    @pytest.mark.asyncio
    async def test_cached_stocks_count_as_success(self) -> None:
        factory, _ = _session_factory()
        trading_patch, latest_patch = _patch_calendar()
        with (
            trading_patch,
            latest_patch,
            patch(
                "collector.spiders.stock_daily_analysis.AsyncSessionLocal", factory
            ),
            patch(
                "collector.spiders.stock_daily_analysis.stock_daily_analysis_service"
                ".list_active_watch_stock_codes",
                AsyncMock(return_value=["600519"]),
            ),
            patch(
                "collector.spiders.stock_daily_analysis.stock_daily_analysis_service"
                ".generate_stock_analysis",
                AsyncMock(return_value=_analysis(cached=True)),
            ),
        ):
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        assert result.items_stored == 0
        assert result.metadata["cached"] == 1

    @pytest.mark.asyncio
    async def test_single_stock_failure_rolls_back_and_continues(self) -> None:
        factory, session = _session_factory()
        trading_patch, latest_patch = _patch_calendar()
        with (
            trading_patch,
            latest_patch,
            patch(
                "collector.spiders.stock_daily_analysis.AsyncSessionLocal", factory
            ),
            patch(
                "collector.spiders.stock_daily_analysis.stock_daily_analysis_service"
                ".list_active_watch_stock_codes",
                AsyncMock(return_value=["600519", "000001"]),
            ),
            patch(
                "collector.spiders.stock_daily_analysis.stock_daily_analysis_service"
                ".generate_stock_analysis",
                AsyncMock(
                    side_effect=[RuntimeError("LLM timeout"), _analysis(cached=False)]
                ),
            ),
        ):
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        assert result.metadata["stocks"]["600519"].startswith("failed:")
        assert result.metadata["stocks"]["000001"] == "generated"
        session.rollback.assert_awaited_once()
