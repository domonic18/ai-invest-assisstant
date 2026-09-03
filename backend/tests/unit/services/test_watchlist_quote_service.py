"""自选股行情服务单测：名称兜底、分钟 trend 降采样。"""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.user import watchlist_quote_service as wsvc


def _scalars_result(rows: list) -> MagicMock:
    return MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=rows)))
    )


def _watch(code: str) -> MagicMock:
    watch = MagicMock()
    watch.stock_code = code
    watch.tags = []
    return watch


@pytest.mark.unit
class TestGetWatchlistQuotes:
    @pytest.mark.asyncio
    async def test_redis_hit_prefers_snapshot_name(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _scalars_result([_watch("000001")])

        redis = AsyncMock()
        redis.get.return_value = (
            b'{"stock_name":"\xe5\xb9\xb3\xe5\xae\x89\xe9\x93\xb6\xe8\xa1\x8c",'
            b'"price":12.5,"change_pct":1.2,"amount":1e8,"updated_at":"2026-09-02"}'
        )
        bars = [SimpleNamespace(stock_code="000001", close=float(i + 1)) for i in range(30)]

        with (
            patch.object(wsvc, "get_redis", MagicMock(return_value=redis)),
            patch.object(
                wsvc, "_load_stock_names", AsyncMock(return_value={"000001": "基本表名称"})
            ),
            patch.object(
                wsvc.trade_calendar_service,
                "resolve_latest_trade_date",
                AsyncMock(return_value=date(2026, 9, 2)),
            ),
            patch.object(wsvc, "fetch_minute_bars_multi", AsyncMock(return_value=bars)),
        ):
            quotes = await wsvc.get_watchlist_quotes(session, user_id=1)

        assert len(quotes) == 1
        assert quotes[0].name == "平安银行"
        assert quotes[0].price == 12.5
        assert quotes[0].change_pct == 1.2
        assert len(quotes[0].trend) == 30
        # 共享 Redis 客户端复用连接，单次查询后不应关闭
        redis.close.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_fallback_uses_stock_basic_name_and_kline(self) -> None:
        kline = MagicMock()
        kline.close = 10.5
        kline.change_pct = -0.5
        kline.amount = 5_000_000.0
        kline.trade_date = date(2026, 7, 16)

        session = AsyncMock()
        session.execute.side_effect = [
            _scalars_result([_watch("600000")]),
            MagicMock(scalar_one_or_none=MagicMock(return_value=kline)),
        ]

        redis = AsyncMock()
        redis.get.return_value = None

        with (
            patch.object(wsvc, "get_redis", MagicMock(return_value=redis)),
            patch.object(
                wsvc, "_load_stock_names", AsyncMock(return_value={"600000": "浦发银行"})
            ),
            patch.object(
                wsvc.trade_calendar_service,
                "resolve_latest_trade_date",
                AsyncMock(return_value=date(2026, 9, 2)),
            ),
            patch.object(wsvc, "fetch_minute_bars_multi", AsyncMock(return_value=[])),
        ):
            quotes = await wsvc.get_watchlist_quotes(session, user_id=1)

        assert quotes[0].name == "浦发银行"
        assert quotes[0].price == 10.5
        assert quotes[0].change_pct == -0.5
        assert quotes[0].updated_at == "2026-07-16"
        assert quotes[0].trend == []

    @pytest.mark.asyncio
    async def test_trend_downsample_preserves_endpoints(self) -> None:
        session = AsyncMock()
        session.execute.side_effect = [
            _scalars_result([_watch("600000")]),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        ]
        redis = AsyncMock()
        redis.get.return_value = None
        bars = [SimpleNamespace(stock_code="600000", close=float(i + 1)) for i in range(121)]

        with (
            patch.object(wsvc, "get_redis", MagicMock(return_value=redis)),
            patch.object(wsvc, "_load_stock_names", AsyncMock(return_value={})),
            patch.object(
                wsvc.trade_calendar_service,
                "resolve_latest_trade_date",
                AsyncMock(return_value=date(2026, 9, 2)),
            ),
            patch.object(wsvc, "fetch_minute_bars_multi", AsyncMock(return_value=bars)),
        ):
            quotes = await wsvc.get_watchlist_quotes(session, user_id=1)

        trend = quotes[0].trend
        assert len(trend) == 60
        assert trend[0] == 1.0
        assert trend[-1] == 121.0

    @pytest.mark.asyncio
    async def test_empty_watchlist_returns_empty(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _scalars_result([])
        redis = AsyncMock()
        names = AsyncMock()

        with (
            patch.object(wsvc, "get_redis", MagicMock(return_value=redis)),
            patch.object(wsvc, "_load_stock_names", names),
        ):
            quotes = await wsvc.get_watchlist_quotes(session, user_id=1)

        assert quotes == []
        names.assert_not_awaited()
