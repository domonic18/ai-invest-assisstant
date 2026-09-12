"""K 线家族 spider 契约测试（transform/validate/store 与数据口径守卫）。"""


import contextlib
import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from collector.spiders.eastmoney_a50_kline import EastmoneyA50KlineCollector
from collector.spiders.sina_etf_kline import SinaEtfKlineCollector
from collector.spiders.sina_index_kline import SinaIndexKlineCollector
from collector.spiders.sina_kline import SinaKlineCollector, _fetch_watchlist_codes


@pytest.mark.unit
class TestSinaKlineCollector:
    @pytest.mark.asyncio
    async def test_transform_and_validate(self) -> None:
        collector = SinaKlineCollector({"source": "sina", "data_type": "quote_kline_stock_daily"})
        raw = {
            "stock_code": "000001",
            "trade_date": "2024-01-02",
            "open": 10.5,
            "high": 11.0,
            "low": 10.2,
            "close": 10.8,
            "volume": 100000,
            "amount": 1080000.0,
            "amplitude": None,
            "change_pct": None,
            "turnover_rate": 0.52,
        }
        item = await collector.transform(raw)
        assert item["close"] == 10.8
        assert item["volume"] == 100000
        assert await collector.validate(item) is True

    @pytest.mark.asyncio
    async def test_fetch_watchlist_codes_dedup_sorted(self) -> None:
        result = MagicMock(all=MagicMock(return_value=[("000001",), ("600519",)]))
        session = AsyncMock()
        session.execute = AsyncMock(return_value=result)

        @contextlib.asynccontextmanager
        async def _cm():
            yield session

        def _fake_session_maker(*_args: object, **_kwargs: object):
            return lambda: _cm()

        with patch(
            "collector.spiders.sina_kline.async_sessionmaker", _fake_session_maker
        ):
            codes = await _fetch_watchlist_codes()

        assert codes == ["000001", "600519"]


@pytest.mark.unit
class TestSinaIndexKlineCollector:
    @pytest.mark.asyncio
    async def test_collect_defaults_to_index_codes(self) -> None:
        from app.core.constants import INDEX_CODES

        collector = SinaIndexKlineCollector(
            {"source": "sina", "data_type": "index_kline"}
        )
        mock_df = pd.DataFrame(
            [
                {
                    "date": "2024-01-02",
                    "open": 2900.0,
                    "high": 2950.0,
                    "low": 2890.0,
                    "close": 2940.0,
                    "volume": 300000000,
                }
            ]
        )
        with (
            patch(
                "akshare.stock_zh_index_daily", return_value=mock_df
            ) as mock_fetch,
            patch(
                "collector.spiders.sina_index_kline.fetch_tracked_extra_codes",
                AsyncMock(return_value=[]),
            ),
        ):
            raw = await collector.collect()

        assert mock_fetch.call_count == len(INDEX_CODES)
        assert {item["stock_code"] for item in raw} == set(INDEX_CODES)
        item = await collector.transform(raw[0])
        assert item["close"] == 2940.0
        assert item["amount"] is None
        assert item["turnover_rate"] is None
        assert await collector.validate(item) is True

    @pytest.mark.asyncio
    async def test_collect_empty_returns_empty(self) -> None:
        collector = SinaIndexKlineCollector(
            {"source": "sina", "data_type": "index_kline"}
        )
        with patch("akshare.stock_zh_index_daily", return_value=pd.DataFrame()):
            assert await collector.collect(symbols=["sh000001"]) == []


@pytest.mark.unit
class TestSinaEtfKlineCollector:
    @pytest.mark.asyncio
    async def test_collect_maps_etf_daily_rows(self) -> None:
        collector = SinaEtfKlineCollector({"source": "sina", "data_type": "etf-kline"})
        mock_df = pd.DataFrame(
            [
                {
                    "date": "2026-07-20",
                    "open": 4.63,
                    "high": 4.685,
                    "low": 4.577,
                    "close": 4.65,
                    "volume": 4010453802,
                    "amount": 18562451759.0,
                }
            ]
        )
        with (
            patch(
                "akshare.fund_etf_hist_sina", return_value=mock_df
            ) as mock_fetch,
            patch(
                "collector.spiders.sina_etf_kline.fetch_tracked_extra_codes",
                AsyncMock(return_value=[]),
            ),
        ):
            raw = await collector.collect()

        mock_fetch.assert_called_once_with(symbol="sh510300")
        assert raw[0]["stock_code"] == "sh510300"
        assert raw[0]["trade_date"] == "2026-07-20"
        item = await collector.transform(raw[0])
        assert item["close"] == 4.65
        assert item["amount"] == 18562451759.0
        assert await collector.validate(item) is True

    @pytest.mark.asyncio
    async def test_collect_empty_returns_empty(self) -> None:
        collector = SinaEtfKlineCollector({"source": "sina", "data_type": "etf-kline"})
        with (
            patch("akshare.fund_etf_hist_sina", return_value=pd.DataFrame()),
            patch(
                "collector.spiders.sina_etf_kline.fetch_tracked_extra_codes",
                AsyncMock(return_value=[]),
            ),
        ):
            assert await collector.collect() == []


@pytest.mark.unit
class TestEastmoneyA50KlineCollector:
    @pytest.mark.asyncio
    async def test_collect_parses_kline_csv(self) -> None:
        collector = EastmoneyA50KlineCollector(
            {"source": "eastmoney", "data_type": "a50-kline"}
        )
        response = MagicMock()
        response.json.return_value = {
            "data": {
                "klines": [
                    "2026-07-20,14827.0,14846.0,14860.0,14795.0,43201",
                    "bad,row",
                ]
            }
        }
        with patch(
            "collector.spiders.eastmoney_a50_kline.eastmoney_get",
            return_value=response,
        ):
            raw = await collector.collect()

        assert len(raw) == 1
        assert raw[0] == {
            "stock_code": "CN00Y",
            "trade_date": datetime.date(2026, 7, 20),
            "open": "14827.0",
            "close": "14846.0",
            "high": "14860.0",
            "low": "14795.0",
            "volume": "43201",
            "amount": None,
        }
        item = await collector.transform(raw[0])
        assert item["close"] == 14846.0
        assert await collector.validate(item) is True

    @pytest.mark.asyncio
    async def test_collect_empty_data_returns_empty(self) -> None:
        collector = EastmoneyA50KlineCollector(
            {"source": "eastmoney", "data_type": "a50-kline"}
        )
        response = MagicMock()
        response.json.return_value = {"data": None}
        with patch(
            "collector.spiders.eastmoney_a50_kline.eastmoney_get",
            return_value=response,
        ):
            assert await collector.collect() == []
