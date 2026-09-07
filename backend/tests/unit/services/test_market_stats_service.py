"""市场统计服务（market_stats_service）契约测试。

测试 patch 目标按函数实际定义模块定向。"""


from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.market import (
    market_service,
    market_stats_service,
    trade_calendar_service,
)


def _scalars_result(items):
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    return result


@pytest.mark.unit
class TestAmountPair:
    """官方成交额只读 market_amount：最新两行即当日与前一有数据交易日。"""

    @pytest.mark.asyncio
    async def test_returns_latest_two_rows(self) -> None:
        rows = [
            MagicMock(amount=Decimal("2660000000000")),
            MagicMock(amount=Decimal("2410000000000")),
        ]
        session = AsyncMock()
        session.execute.return_value = _scalars_result(rows)

        amount, prev = await market_service._amount_pair(session, date(2026, 7, 17))

        assert amount == 2.66e12
        assert prev == 2.41e12

    @pytest.mark.asyncio
    async def test_empty_returns_none_pair(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _scalars_result([])

        assert await market_service._amount_pair(session, date(2026, 7, 17)) == (
            None,
            None,
        )


@pytest.mark.unit
class TestHistoricalBreadth:
    @pytest.mark.asyncio
    async def test_prefers_market_breadth_row(self) -> None:
        """market_breadth 有当日行且涨停池未覆盖时返回行内全量统计。"""
        session = AsyncMock()
        row = MagicMock(
            up_count=3000,
            down_count=1800,
            flat_count=200,
            limit_up_count=55,
            limit_down_count=12,
        )
        # 第一次 scalar 查 market_breadth 行，第二次查涨停池家数（未覆盖）
        session.scalar.side_effect = [row, None]

        breadth = await market_service._historical_breadth(
            session, date(2026, 7, 17)
        )

        assert breadth == {
            "up_count": 3000,
            "down_count": 1800,
            "flat_count": 200,
            "limit_up_count": 55,
            "limit_down_count": 12,
        }

    @pytest.mark.asyncio
    async def test_pool_count_overrides_row_limit_up(self) -> None:
        """涨停池已覆盖当日时，涨停数覆盖为池计数（官方池口径，不含 ST）。"""
        session = AsyncMock()
        row = MagicMock(
            up_count=3000,
            down_count=1800,
            flat_count=200,
            limit_up_count=55,
            limit_down_count=12,
        )
        session.scalar.side_effect = [row, 53]

        breadth = await market_service._historical_breadth(
            session, date(2026, 7, 17)
        )

        assert breadth["limit_up_count"] == 53
        assert breadth["limit_down_count"] == 12

    @pytest.mark.asyncio
    async def test_falls_back_to_limit_up_pool_count(self) -> None:
        """表内无当日行时：涨停数取 pool_limit_up_stock 计数，其余为空口径。"""
        session = AsyncMock()
        # 第一次 scalar 查 market_breadth 行（无），第二次查涨停池家数
        session.scalar.side_effect = [None, 42]

        breadth = await market_service._historical_breadth(
            session, date(2026, 7, 16)
        )

        assert breadth["limit_up_count"] == 42
        assert breadth["limit_down_count"] == 0
        assert breadth["up_count"] is None
        assert breadth["down_count"] is None

    @pytest.mark.asyncio
    async def test_all_null_breadth_row_falls_back(self) -> None:
        """非交易日运行残留的全空 breadth 行视为无数据，回退涨停池计数。"""
        session = AsyncMock()
        row = MagicMock(
            up_count=None,
            down_count=None,
            flat_count=None,
            limit_up_count=None,
            limit_down_count=None,
        )
        session.scalar.side_effect = [row, 33]

        breadth = await market_service._historical_breadth(
            session, date(2026, 7, 17)
        )

        assert breadth["limit_up_count"] == 33
        assert breadth["up_count"] is None

    @pytest.mark.asyncio
    async def test_fallback_preserves_row_limit_down_count(self) -> None:
        """回退合并时保留行内跌停数（limit-down-pool 补采写入）。"""
        session = AsyncMock()
        row = MagicMock(
            up_count=None,
            down_count=None,
            flat_count=None,
            limit_up_count=None,
            limit_down_count=9,
        )
        session.scalar.side_effect = [row, 33]

        breadth = await market_service._historical_breadth(
            session, date(2026, 7, 17)
        )

        assert breadth["limit_up_count"] == 33
        assert breadth["limit_down_count"] == 9

    @pytest.mark.asyncio
    async def test_historical_stats_without_emotion(self) -> None:
        session = AsyncMock()
        with (
            patch.object(
                trade_calendar_service,
                "resolve_latest_trade_date",
                AsyncMock(return_value=date(2026, 7, 17)),
            ),
            patch.object(
                market_stats_service,
                "_historical_breadth",
                AsyncMock(
                    return_value={
                        "up_count": None,
                        "down_count": None,
                        "flat_count": None,
                        "limit_up_count": 42,
                        "limit_down_count": 33,
                    }
                ),
            ),
            patch.object(
                market_stats_service,
                "_amount_pair",
                AsyncMock(return_value=(2.4e12, 2.2e12)),
            ),
            patch.object(
                market_stats_service,
                "_limit_up_rates",
                AsyncMock(return_value=(0.3, 0.2, 8)),
            ),
        ):
            stats = await market_service.get_market_stats(session, date(2026, 7, 16))

        assert stats.trade_date == date(2026, 7, 16)
        assert stats.up_count is None
        assert stats.limit_up_count == 42
        assert stats.limit_down_count == 33
        assert stats.emotion_score is None
        assert stats.emotion_label is None
        assert stats.amount == 2.4e12
        assert stats.amount_change_pct == pytest.approx(9.09, abs=0.01)


@pytest.mark.unit
class TestEmotionScore:
    def test_hot_market_scores_high(self) -> None:
        score, ratio = market_service._emotion_score(
            up=2847, down=1562, flat=100, limit_up=128,
            continuous_rate=0.36, broken_rate=0.18,
        )
        assert score > 60
        assert ratio == pytest.approx(2.84, abs=0.01)

    def test_cold_market_scores_low(self) -> None:
        score, _ = market_service._emotion_score(
            up=400, down=4700, flat=50, limit_up=10,
            continuous_rate=0.10, broken_rate=0.45,
        )
        assert score < 40

    def test_clamped_to_bounds(self) -> None:
        score, _ = market_service._emotion_score(
            up=5000, down=0, flat=0, limit_up=500,
            continuous_rate=1.0, broken_rate=0.0,
        )
        assert 0 <= score <= 100


@pytest.mark.unit
class TestLiveBreadth:
    """当日涨跌统计只读 market_breadth 表：最新行直返、无行返回空统计。"""

    @pytest.mark.asyncio
    async def test_returns_latest_row(self) -> None:
        session = AsyncMock()
        row = MagicMock(
            up_count=2500,
            down_count=2100,
            flat_count=300,
            limit_up_count=60,
            limit_down_count=15,
        )
        # 第一次 scalar 查 market_breadth 最新行，第二次查涨停池家数（未覆盖）
        session.scalar.side_effect = [row, None]

        breadth = await market_service._live_breadth(session, date(2026, 7, 17))

        assert breadth == {
            "up_count": 2500,
            "down_count": 2100,
            "flat_count": 300,
            "limit_up_count": 60,
            "limit_down_count": 15,
        }

    @pytest.mark.asyncio
    async def test_pool_count_overrides_snapshot_limit_up(self) -> None:
        """涨停池入库后，当日涨停数覆盖为池计数（快照估算仅盘中使用）。"""
        session = AsyncMock()
        row = MagicMock(
            up_count=2500,
            down_count=2100,
            flat_count=300,
            limit_up_count=60,
            limit_down_count=15,
        )
        session.scalar.side_effect = [row, 53]

        breadth = await market_service._live_breadth(session, date(2026, 7, 17))

        assert breadth["limit_up_count"] == 53
        assert breadth["limit_down_count"] == 15

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_row(self) -> None:
        session = AsyncMock()
        session.scalar.return_value = None

        breadth = await market_service._live_breadth(session, date(2026, 7, 17))

        assert breadth["up_count"] is None
        assert breadth["down_count"] is None
        assert breadth["limit_up_count"] == 0
        assert breadth["limit_down_count"] == 0
