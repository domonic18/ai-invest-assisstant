"""盘中行情与市场统计 spider 契约测试（transform/validate/store 与数据口径守卫）。"""


import contextlib
import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from collector.core.calendar import latest_trading_day
from collector.spiders.exchange_market_amount import ExchangeMarketAmountCollector
from collector.spiders.sina_index_minute import SinaIndexMinuteCollector
from collector.spiders.sina_index_spot import SinaIndexSpotCollector
from collector.spiders.sina_market_breadth import (
    SinaMarketBreadthCollector,
    count_breadth,
)
from collector.spiders.sina_quote import SinaQuoteCollector
from collector.spiders.sina_stock_minute import SinaStockMinuteCollector, _fetch_default_codes


@pytest.mark.unit
class TestSinaQuoteCollector:
    @pytest.mark.asyncio
    async def test_transform_and_validate(self) -> None:
        collector = SinaQuoteCollector({"source": "sina", "data_type": "quote"})
        raw = {
            "stock_code": "000001",
            "stock_name": "平安银行",
            "price": 10.5,
            "change": 0.2,
            "change_pct": 1.94,
            "bid": 10.49,
            "ask": 10.5,
            "prev_close": 10.3,
            "open": 10.3,
            "high": 10.6,
            "low": 10.2,
            "volume": 100000.0,
            "amount": 1050000.0,
            "timestamp": "15:20:34",
            "updated_at": "2024-01-02T15:20:34",
        }
        item = await collector.transform(raw)
        assert item["stock_code"] == "000001"
        assert item["price"] == 10.5
        assert await collector.validate(item) is True

    @pytest.mark.asyncio
    async def test_validate_rejects_zero_price(self) -> None:
        collector = SinaQuoteCollector({"source": "sina", "data_type": "quote"})
        item = {"stock_code": "000001", "price": 0.0}
        assert await collector.validate(item) is False

    @pytest.mark.asyncio
    async def test_collect_filters_symbols(self) -> None:
        collector = SinaQuoteCollector({"source": "sina", "data_type": "quote"})
        mock_df = pd.DataFrame(
            [
                {
                    "代码": "sh000001",
                    "名称": "平安银行",
                    "最新价": 10.5,
                    "涨跌额": 0.2,
                    "涨跌幅": 1.94,
                    "买入": 10.49,
                    "卖出": 10.5,
                    "昨收": 10.3,
                    "今开": 10.3,
                    "最高": 10.6,
                    "最低": 10.2,
                    "成交量": 100000.0,
                    "成交额": 1050000.0,
                    "时间戳": "15:20:34",
                },
                {
                    "代码": "sz000002",
                    "名称": "万科A",
                    "最新价": 15.0,
                    "涨跌额": -0.1,
                    "涨跌幅": -0.66,
                    "买入": 14.99,
                    "卖出": 15.0,
                    "昨收": 15.1,
                    "今开": 15.1,
                    "最高": 15.2,
                    "最低": 14.9,
                    "成交量": 200000.0,
                    "成交额": 3000000.0,
                    "时间戳": "15:20:34",
                },
            ]
        )

        with patch("akshare.stock_zh_a_spot", return_value=mock_df):
            raw = await collector.collect(symbols=["000001"])

        assert len(raw) == 1
        assert raw[0]["stock_code"] == "000001"

    @pytest.mark.asyncio
    async def test_store_writes_to_redis(self) -> None:
        collector = SinaQuoteCollector(
            {"source": "sina", "data_type": "quote", "ttl_seconds": 60}
        )
        items = [
            {
                "stock_code": "000001",
                "stock_name": "平安银行",
                "price": 10.5,
                "change": 0.2,
                "change_pct": 1.94,
                "bid": 10.49,
                "ask": 10.5,
                "prev_close": 10.3,
                "open": 10.3,
                "high": 10.6,
                "low": 10.2,
                "volume": 100000.0,
                "amount": 1050000.0,
                "timestamp": "15:20:34",
                "updated_at": "2024-01-02T15:20:34",
            }
        ]

        mock_redis = AsyncMock()
        mock_redis.close = AsyncMock()
        with patch("redis.asyncio.from_url", return_value=mock_redis):
            count = await collector.store(items)

        assert count == 1
        assert mock_redis.setex.await_count == 2
        writes = {args.args[0]: (args.args[1], args.args[2]) for args in mock_redis.setex.await_args_list}
        assert set(writes) == {"quote:000001", "quote:eod:000001"}
        assert writes["quote:000001"][0] == 60
        # 收盘兜底键默认 4 天，覆盖周末与节假日
        assert writes["quote:eod:000001"][0] == 4 * 86400
        assert "000001" in writes["quote:eod:000001"][1]


@pytest.mark.unit
class TestCountBreadth:
    def _row(
        self,
        code: str,
        name: str,
        pct: float,
        price: float,
        high: float,
        low: float,
    ) -> dict:
        return {
            "代码": code,
            "名称": name,
            "最新价": price,
            "涨跌幅": pct,
            "最高": high,
            "最低": low,
            "时间戳": "15:30:01",
        }

    def test_counts_up_down_flat(self) -> None:
        df = pd.DataFrame(
            [
                self._row("sh600001", "甲", 1.0, 10.0, 10.5, 9.8),
                self._row("sz000001", "乙", -2.0, 9.0, 9.5, 8.9),
                self._row("bj920001", "丙", 0.0, 5.0, 5.1, 4.9),
                self._row("sh600002", "丁", float("nan"), 0.0, 0.0, 0.0),
            ]
        )
        result = count_breadth(df)

        assert result["up_count"] == 1
        assert result["down_count"] == 1
        assert result["flat_count"] == 1

    def test_sealed_limit_up_down_by_board(self) -> None:
        df = pd.DataFrame(
            [
                # 主板封板涨停 / 触板未封（收盘未在最高价）
                self._row("sh600001", "甲", 10.0, 11.0, 11.0, 10.0),
                self._row("sh600002", "乙", 10.0, 10.9, 11.0, 10.0),
                # 创业板 20% 封板
                self._row("sz300001", "丙", 20.0, 12.0, 12.0, 10.5),
                # 科创板 20% 封板
                self._row("sh688001", "丁", 19.9, 11.98, 11.98, 10.0),
                # 北交所 30% 封板
                self._row("bj920001", "戊", 30.0, 13.0, 13.0, 9.5),
                # ST 5% 封板
                self._row("sh600003", "ST己", 5.0, 10.5, 10.5, 9.9),
                # 主板封板跌停 / ST 封板跌停
                self._row("sz000002", "庚", -10.0, 9.0, 9.5, 9.0),
                self._row("sz000003", "*ST辛", -5.0, 9.5, 10.0, 9.5),
            ]
        )
        result = count_breadth(df)

        assert result["limit_up_count"] == 5
        assert result["limit_down_count"] == 2


@pytest.mark.unit
class TestSinaMarketBreadthCollector:
    @pytest.mark.asyncio
    async def test_collect_returns_single_daily_row(self) -> None:
        collector = SinaMarketBreadthCollector(
            {"source": "sina", "data_type": "market-breadth"}
        )
        mock_df = pd.DataFrame(
            [
                {
                    "代码": "sh600001",
                    "名称": "甲",
                    "最新价": 11.0,
                    "涨跌幅": 10.0,
                    "最高": 11.0,
                    "最低": 10.0,
                    "时间戳": "15:30:01",
                },
                {
                    "代码": "sz000001",
                    "名称": "乙",
                    "最新价": 9.0,
                    "涨跌幅": -2.0,
                    "最高": 9.5,
                    "最低": 8.9,
                    "时间戳": "15:30:01",
                },
            ]
        )
        with patch("akshare.stock_zh_a_spot", return_value=mock_df):
            raw = await collector.collect(trade_date=latest_trading_day())

        assert len(raw) == 1
        item = raw[0]
        assert item["trade_date"] == latest_trading_day()
        assert item["up_count"] == 1
        assert item["down_count"] == 1
        assert item["limit_up_count"] == 1
        assert item["limit_down_count"] == 0
        assert item["source"] == "sina"

    @pytest.mark.asyncio
    async def test_collect_empty_snapshot_returns_empty(self) -> None:
        collector = SinaMarketBreadthCollector(
            {"source": "sina", "data_type": "market-breadth"}
        )
        with patch("akshare.stock_zh_a_spot", return_value=pd.DataFrame()):
            assert await collector.collect() == []


@pytest.mark.unit
class TestSinaIndexSpotCollector:
    @pytest.mark.asyncio
    async def test_collect_filters_index_codes(self) -> None:
        collector = SinaIndexSpotCollector({"source": "sina", "data_type": "index-spot"})
        mock_df = pd.DataFrame(
            [
                {
                    "代码": "sh000001",
                    "名称": "上证指数",
                    "最新价": 3801.5,
                    "涨跌额": 20.5,
                    "涨跌幅": 0.54,
                    "成交量": 3e8,
                    "成交额": 5e11,
                    "时间": "15:00:00",
                },
                {"代码": "sh000300", "名称": "沪深300", "最新价": 1.0,
                 "涨跌额": 0.0, "涨跌幅": 0.0, "成交量": 1.0, "成交额": 1.0,
                 "时间": "15:00:00"},
            ]
        )
        with patch("akshare.stock_zh_index_spot_sina", return_value=mock_df):
            raw = await collector.collect()

        # 只保留 INDEX_CODES 中的四个指数，沪深300 被过滤
        assert {item["code"] for item in raw} == {"sh000001"}
        assert raw[0]["amount"] == 5e11

    @pytest.mark.asyncio
    async def test_store_writes_redis_single_key(self) -> None:
        collector = SinaIndexSpotCollector({"source": "sina", "data_type": "index-spot"})
        redis = AsyncMock()
        with patch("redis.asyncio.from_url", return_value=redis):
            stored = await collector.store([{"code": "sh000001", "price": 1.0}])

        assert stored == 1
        assert redis.setex.await_args.args[0] == "market:index_spot"
        redis.close.assert_awaited_once()


@pytest.mark.unit
class TestSinaIndexMinuteCollector:
    @pytest.mark.asyncio
    async def test_collect_keeps_only_target_day(self) -> None:
        collector = SinaIndexMinuteCollector(
            {"source": "sina", "data_type": "index-minute"}
        )
        mock_df = pd.DataFrame(
            [
                {"day": "2026-07-16 15:00:00", "open": 1.0, "high": 1.0,
                 "low": 1.0, "close": 101.0, "volume": 1.0, "amount": 2.0},
                {"day": "2026-07-17 09:31:00", "open": 1.0, "high": 1.0,
                 "low": 1.0, "close": 102.0, "volume": 1.0, "amount": 2.0},
            ]
        )
        with patch("akshare.stock_zh_a_minute", return_value=mock_df):
            raw = await collector.collect(
                symbols=["sh000001"], trade_date=datetime.date(2026, 7, 17)
            )

        assert len(raw) == 1
        assert raw[0]["stock_code"] == "sh000001"
        assert raw[0]["trade_time"].date() == datetime.date(2026, 7, 17)
        assert raw[0]["trade_time"].tzinfo is not None


@pytest.mark.unit
class TestSinaStockMinuteCollector:
    def _df(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"day": "2026-07-20 15:00:00", "open": 1.0, "high": 1.0,
                 "low": 1.0, "close": 10.0, "volume": 1.0, "amount": 2.0},
                {"day": "2026-07-21 09:31:00", "open": 1.0, "high": 1.0,
                 "low": 1.0, "close": 11.0, "volume": 1.0, "amount": 2.0},
            ]
        )

    @pytest.mark.asyncio
    async def test_collect_prefixes_codes_and_filters_target_day(self) -> None:
        collector = SinaStockMinuteCollector(
            {"source": "sina", "data_type": "stock-minute"}
        )
        with patch(
            "akshare.stock_zh_a_minute", return_value=self._df()
        ) as mock_minute:
            raw = await collector.collect(
                symbols=["600001", "000001"], trade_date=datetime.date(2026, 7, 21)
            )

        called_symbols = [call.kwargs["symbol"] for call in mock_minute.call_args_list]
        assert called_symbols == ["sh600001", "sz000001"]
        # 只保留目标日，两只各 1 条
        assert len(raw) == 2
        assert {item["stock_code"] for item in raw} == {"600001", "000001"}
        assert all(
            item["trade_time"].date() == datetime.date(2026, 7, 21) for item in raw
        )

    @pytest.mark.asyncio
    async def test_collect_skips_bse_and_survives_single_failure(self) -> None:
        collector = SinaStockMinuteCollector(
            {"source": "sina", "data_type": "stock-minute"}
        )

        def _side_effect(symbol: str, **kwargs):
            if symbol == "sz000001":
                raise ConnectionError("rate limited")
            return self._df()

        with patch("akshare.stock_zh_a_minute", side_effect=_side_effect) as mock_minute:
            raw = await collector.collect(
                symbols=["430001", "000001", "600001"],
                trade_date=datetime.date(2026, 7, 21),
            )

        # 北交所（4 开头）不请求；000001 失败不影响 600001
        called_symbols = [call.kwargs["symbol"] for call in mock_minute.call_args_list]
        assert called_symbols == ["sz000001", "sh600001"]
        assert {item["stock_code"] for item in raw} == {"600001"}

    @pytest.mark.asyncio
    async def test_collect_defaults_to_limit_up_pool_codes(self) -> None:
        collector = SinaStockMinuteCollector(
            {"source": "sina", "data_type": "stock-minute"}
        )
        with (
            patch(
                "collector.spiders.sina_stock_minute._fetch_default_codes",
                AsyncMock(return_value=["600001"]),
            ),
            patch("akshare.stock_zh_a_minute", return_value=self._df()),
        ):
            raw = await collector.collect(trade_date=datetime.date(2026, 7, 21))

        assert {item["stock_code"] for item in raw} == {"600001"}

    @pytest.mark.asyncio
    async def test_default_codes_union_watchlist_dedup(self) -> None:
        pool_result = MagicMock(all=MagicMock(return_value=[("600001",), ("600002",)]))
        watch_result = MagicMock(
            all=MagicMock(return_value=[("600002",), ("603221",), ("830001",)])
        )
        session = AsyncMock()
        session.execute.side_effect = [pool_result, watch_result]

        @contextlib.asynccontextmanager
        async def _cm():
            yield session

        def _fake_session_maker(*_args: object, **_kwargs: object):
            return lambda: _cm()

        with patch(
            "collector.spiders.sina_stock_minute.async_sessionmaker", _fake_session_maker
        ):
            codes = await _fetch_default_codes(datetime.date(2026, 9, 3))

        assert codes == ["600001", "600002", "603221", "830001"]


@pytest.mark.unit
class TestExchangeMarketAmountCollector:
    @pytest.mark.asyncio
    async def test_collect_sums_sse_and_szse(self) -> None:
        collector = ExchangeMarketAmountCollector(
            {"source": "exchange", "data_type": "market-amount"}
        )
        sse_df = pd.DataFrame(
            {"单日情况": ["成交金额"], "股票": [5000.0]}  # 亿元
        )
        szse_df = pd.DataFrame(
            {"证券类别": ["股票"], "成交金额": [6e11]}  # 元
        )
        with (
            patch("akshare.stock_sse_deal_daily", return_value=sse_df),
            patch("akshare.stock_szse_summary", return_value=szse_df),
        ):
            raw = await collector.collect(trade_date=datetime.date(2026, 7, 17))

        assert len(raw) == 1
        assert raw[0]["trade_date"] == datetime.date(2026, 7, 17)
        assert raw[0]["amount"] == 5000.0 * 1e8 + 6e11
        assert raw[0]["source"] == "exchange"

    @pytest.mark.asyncio
    async def test_collect_unpublished_returns_empty(self) -> None:
        collector = ExchangeMarketAmountCollector(
            {"source": "exchange", "data_type": "market-amount"}
        )
        with patch(
            "akshare.stock_sse_deal_daily", side_effect=ValueError("no data")
        ):
            assert await collector.collect(
                trade_date=datetime.date(2026, 7, 17)
            ) == []
