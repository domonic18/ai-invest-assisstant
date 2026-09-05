"""日 K 新鲜度自愈采集器契约测试（已齐跳过/缺失自愈/重跑后仍缺/盘中跳过）。"""

from contextlib import ExitStack
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from app.core.constants import INDEX_CODES
from collector.core.base import CollectStatus
from collector.spiders.kline_freshness import (
    A50_CODE,
    KlineFreshnessCollector,
)
from collector.spiders.sina_etf_kline import SinaEtfKlineCollector

_EXPECTED = date(2026, 9, 4)
_TODAY = date(2026, 9, 5)
_CN_TZ = ZoneInfo("Asia/Shanghai")
_WATCHLIST = ["002900", "600519"]
# 指数/ETF/A50/部分自选股初始齐全的基准集合（002900 留给用例控制）
_BASE_FRESH = {*INDEX_CODES, *SinaEtfKlineCollector.symbols, A50_CODE, "600519"}

_CFG = {"source": "internal", "data_type": "kline_freshness"}


def _session_factory_mock() -> MagicMock:
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory


def _enter_common_patches(
    stack: ExitStack,
    *,
    latest: date = _EXPECTED,
    now_hour: int = 11,
    fresh: set[str],
    rerun: AsyncMock | None = None,
) -> AsyncMock:
    """登记公共 patch：日历/时钟/自选股/日K存在性/会话工厂；返回 rerun mock。"""
    stack.enter_context(
        patch(
            "collector.spiders.kline_freshness.latest_trading_day",
            return_value=latest,
        )
    )
    stack.enter_context(
        patch("collector.spiders.kline_freshness.today_cn", return_value=_TODAY)
    )
    stack.enter_context(
        patch(
            "collector.spiders.kline_freshness.now_cn",
            return_value=datetime(
                _TODAY.year, _TODAY.month, _TODAY.day, now_hour, tzinfo=_CN_TZ
            ),
        )
    )
    stack.enter_context(
        patch(
            "collector.spiders.kline_freshness.KlineFreshnessCollector._watchlist_codes",
            new=AsyncMock(return_value=_WATCHLIST),
        )
    )

    def bar_lookup(_session: object, code: str, _day: date) -> bool:
        return code in fresh

    stack.enter_context(
        patch(
            "collector.spiders.kline_freshness.has_daily_bar",
            AsyncMock(side_effect=bar_lookup),
        )
    )
    stack.enter_context(
        patch(
            "collector.spiders.kline_freshness.AsyncSessionLocal",
            _session_factory_mock(),
        )
    )

    rerun_mock = rerun or AsyncMock()
    stack.enter_context(
        patch(
            "collector.spiders.kline_freshness.KlineFreshnessCollector._rerun",
            new=rerun_mock,
        )
    )
    return rerun_mock


@pytest.mark.unit
class TestKlineFreshnessCollector:
    @pytest.mark.asyncio
    async def test_skips_when_all_fresh(self) -> None:
        collector = KlineFreshnessCollector(_CFG)

        with ExitStack() as stack:
            rerun = _enter_common_patches(stack, fresh={*_BASE_FRESH, "002900"})
            result = await collector.run()

        assert result.status == CollectStatus.SKIPPED
        rerun.assert_not_called()
        assert result.metadata["trade_date"] == _EXPECTED.isoformat()

    @pytest.mark.asyncio
    async def test_heals_missing_watchlist_bar(self) -> None:
        collector = KlineFreshnessCollector(_CFG)
        fresh = set(_BASE_FRESH)
        rerun = AsyncMock()

        async def rerun_marks_fresh(task_name: str, symbols: list[str]) -> None:
            fresh.update(symbols)

        rerun.side_effect = rerun_marks_fresh

        with ExitStack() as stack:
            _enter_common_patches(stack, fresh=fresh, rerun=rerun)
            result = await collector.run()

        assert result.status == CollectStatus.SUCCESS
        rerun.assert_called_once_with("watchlist-kline-daily", ["002900"])

    @pytest.mark.asyncio
    async def test_partial_when_rerun_insufficient(self) -> None:
        collector = KlineFreshnessCollector(_CFG)

        with ExitStack() as stack:
            _enter_common_patches(stack, fresh=set(_BASE_FRESH))
            result = await collector.run()

        assert result.status == CollectStatus.PARTIAL
        assert any("002900" in err for err in result.errors)

    @pytest.mark.asyncio
    async def test_skips_before_publish_time_when_expected_is_today(self) -> None:
        collector = KlineFreshnessCollector(_CFG)

        with ExitStack() as stack:
            rerun = _enter_common_patches(stack, latest=_TODAY, now_hour=10, fresh=set())
            result = await collector.run()

        assert result.status == CollectStatus.SKIPPED
        assert result.errors
        rerun.assert_not_called()
