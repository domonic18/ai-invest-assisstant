"""个股行情服务（stock_service）契约测试。"""


from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.market import (
    stock_service,
)


@pytest.mark.unit
class TestGetStockQuote:
    """个股行情快照：实时键 → 收盘兜底键 → 日 K 三级回退。"""

    def _stock(self) -> MagicMock:
        stock = MagicMock()
        stock.stock_name = "平安银行"
        stock.total_shares = 1000.0
        stock.circulating_shares = 800.0
        return stock

    @pytest.mark.asyncio
    async def test_eod_fallback_when_live_expired(self) -> None:
        """实时键过期（盘后/周末）时读长 TTL 收盘兜底键。"""
        session = AsyncMock()
        redis = AsyncMock()
        redis.mget.return_value = (
            None,
            '{"price":12.0,"prev_close":11.9,"open":11.95,"high":12.1,"low":11.9,'
            '"volume":100000,"amount":1200000,"updated_at":"2026-09-04T15:55"}',
        )
        with (
            patch.object(
                stock_service, "get_stock_by_code", AsyncMock(return_value=self._stock())
            ),
            patch.object(stock_service, "get_redis", MagicMock(return_value=redis)),
        ):
            quote = await stock_service.get_stock_quote(session, "000001")

        assert quote is not None
        assert quote["price"] == 12.0
        assert quote["change"] == round(12.0 - 11.9, 4)
        assert quote["updated_at"] == "2026-09-04T15:55"

    @pytest.mark.asyncio
    async def test_all_miss_returns_empty_quote_not_none(self) -> None:
        """快照与日 K 全 miss（股池外标的周末）：返回空值快照而非 None。"""
        session = AsyncMock()
        redis = AsyncMock()
        redis.mget.return_value = (None, None)
        with (
            patch.object(
                stock_service, "get_stock_by_code", AsyncMock(return_value=self._stock())
            ),
            patch.object(stock_service, "get_redis", MagicMock(return_value=redis)),
            patch.object(stock_service, "fetch_daily_bars", AsyncMock(return_value=[])),
        ):
            quote = await stock_service.get_stock_quote(session, "605577")

        assert quote is not None
        assert quote["name"] == "平安银行"
        assert quote["price"] is None
        assert quote["change"] is None
        assert quote["market_cap"] is None
        assert quote["updated_at"] is None

    @pytest.mark.asyncio
    async def test_kline_fallback_still_used(self) -> None:
        """兜底键也过期时按最近两根日 K 推算。"""
        session = AsyncMock()
        redis = AsyncMock()
        redis.mget.return_value = (None, None)
        latest = SimpleNamespace(
            close=10.5, open=10.2, high=10.8, low=10.1,
            volume=5000, amount=52500.0, trade_date=date(2026, 9, 4),
        )
        prev = SimpleNamespace(close=10.0)
        with (
            patch.object(
                stock_service, "get_stock_by_code", AsyncMock(return_value=self._stock())
            ),
            patch.object(stock_service, "get_redis", MagicMock(return_value=redis)),
            patch.object(
                stock_service, "fetch_daily_bars", AsyncMock(return_value=[latest, prev])
            ),
        ):
            quote = await stock_service.get_stock_quote(session, "000001")

        assert quote["price"] == 10.5
        assert quote["prev_close"] == 10.0
        assert quote["change_pct"] == 5.0
        assert quote["updated_at"] == "2026-09-04"

    @pytest.mark.asyncio
    async def test_unknown_stock_returns_none(self) -> None:
        """股票本身不存在仍返回 None（路由 404）。"""
        session = AsyncMock()
        with patch.object(
            stock_service, "get_stock_by_code", AsyncMock(return_value=None)
        ):
            quote = await stock_service.get_stock_quote(session, "999999")

        assert quote is None


@pytest.mark.unit
class TestBatchQuoteSnapshot:
    """批量轻量快照：名称 + 当日涨跌幅（实时/收盘键 → 日 K 回退）。"""

    @pytest.mark.asyncio
    async def test_live_key_hit_computes_change_pct(self) -> None:
        """实时键命中直接算涨跌幅，不走日 K 回退。"""
        session = AsyncMock()
        redis = AsyncMock()
        # 键序：quote:600115, quote:eod:600115, quote:000001, quote:eod:000001
        redis.mget.return_value = (
            '{"price":10.2,"prev_close":10.0}',
            None,
            None,
            '{"price":5.0,"prev_close":5.0}',
        )
        repo = MagicMock()
        repo.get_names_by_codes = AsyncMock(
            return_value={"600115": "中国东航", "000001": "平安银行"}
        )
        kline = AsyncMock()
        with (
            patch.object(stock_service, "StockRepository", MagicMock(return_value=repo)),
            patch.object(stock_service, "get_redis", MagicMock(return_value=redis)),
            patch.object(stock_service, "fetch_daily_bars_multi", kline),
        ):
            result = await stock_service.batch_quote_snapshot(
                session, ["600115", "000001"]
            )

        assert result["600115"] == {"name": "中国东航", "change_pct": 2.0}
        assert result["000001"] == {"name": "平安银行", "change_pct": 0.0}
        kline.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_kline_fallback_from_latest_two_closes(self) -> None:
        """Redis 全 miss 时用最近两根日 K（升序：末位最新）推算。"""
        session = AsyncMock()
        redis = AsyncMock()
        redis.mget.return_value = (None, None)
        repo = MagicMock()
        repo.get_names_by_codes = AsyncMock(return_value={"600115": "中国东航"})
        bars = [
            SimpleNamespace(close=9.0),
            SimpleNamespace(close=9.9),
        ]
        with (
            patch.object(stock_service, "StockRepository", MagicMock(return_value=repo)),
            patch.object(stock_service, "get_redis", MagicMock(return_value=redis)),
            patch.object(
                stock_service,
                "fetch_daily_bars_multi",
                AsyncMock(return_value={"600115": bars}),
            ),
        ):
            result = await stock_service.batch_quote_snapshot(session, ["600115"])

        assert result["600115"] == {"name": "中国东航", "change_pct": 10.0}

    @pytest.mark.asyncio
    async def test_unknown_code_skipped_and_empty_input(self) -> None:
        """不在 stock_basic 的代码跳过；空入参直接空 dict。"""
        session = AsyncMock()
        repo = MagicMock()
        repo.get_names_by_codes = AsyncMock(return_value={})
        with patch.object(
            stock_service, "StockRepository", MagicMock(return_value=repo)
        ):
            assert await stock_service.batch_quote_snapshot(session, ["sh999999"]) == {}
            assert await stock_service.batch_quote_snapshot(session, []) == {}
