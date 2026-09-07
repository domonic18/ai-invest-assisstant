"""集合竞价 spider 契约测试。"""


import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from collector.spiders.sina_auction import SinaAuctionCollector
from collector.spiders.ths_auction import ThsAuctionCollector
from collector.spiders.tushare_index_auction import TushareIndexAuctionCollector


@pytest.mark.unit
class TestThsAuctionCollector:
    @pytest.mark.asyncio
    async def test_transform_and_validate(self) -> None:
        collector = ThsAuctionCollector({"source": "ths", "data_type": "auction"})
        raw = {
            "stock_code": "000001",
            "trade_date": "2024-01-02",
            "match_time": "09:25:00",
            "最新": 10.8,
            "总手": 50000,
            "buy_1": 10.7,
            "buy_1_vol": 1000,
            "buy_2": 10.6,
            "buy_2_vol": 2000,
            "buy_3": None,
            "buy_3_vol": None,
            "buy_4": 10.5,
            "buy_4_vol": 4000,
            "buy_5": 10.4,
            "buy_5_vol": 5000,
            "sell_1": 10.9,
            "sell_1_vol": 1500,
            "sell_2": 11.0,
            "sell_2_vol": 2500,
            "sell_3": 11.1,
            "sell_3_vol": 3500,
            "sell_4": 11.2,
            "sell_4_vol": 4500,
            "sell_5": 11.3,
            "sell_5_vol": 5500,
        }
        item = await collector.transform(raw)
        assert item["stock_code"] == "000001"
        assert item["price"] == 10.8
        assert item["volume"] == 50000
        assert item["bid_prices"][0] == 10.7
        assert item["bid_prices"][2] is None
        assert await collector.validate(item) is True


@pytest.mark.unit
class TestSinaAuctionCollector:
    @pytest.mark.asyncio
    async def test_transform_and_validate(self) -> None:
        collector = SinaAuctionCollector({"source": "sina", "data_type": "auction"})
        raw = {
            "stock_code": "000001",
            "trade_date": datetime.date(2024, 1, 2),
            "match_time": datetime.time(9, 25, 0),
            "current": 10.8,
            "volume": 50000,
            "buy_1_price": 10.7,
            "buy_1_vol": 1000,
            "buy_2_price": 10.6,
            "buy_2_vol": 2000,
            "buy_3_price": None,
            "buy_3_vol": None,
            "buy_4_price": 10.5,
            "buy_4_vol": 4000,
            "buy_5_price": 10.4,
            "buy_5_vol": 5000,
            "sell_1_price": 10.9,
            "sell_1_vol": 1500,
            "sell_2_price": 11.0,
            "sell_2_vol": 2500,
            "sell_3_price": 11.1,
            "sell_3_vol": 3500,
            "sell_4_price": 11.2,
            "sell_4_vol": 4500,
            "sell_5_price": 11.3,
            "sell_5_vol": 5500,
        }
        item = await collector.transform(raw)
        assert item["stock_code"] == "000001"
        assert item["price"] == 10.8
        assert item["volume"] == 50000
        assert item["bid_prices"][0] == 10.7
        assert item["bid_prices"][2] is None
        assert await collector.validate(item) is True

    @pytest.mark.asyncio
    async def test_fetch_snapshot_handles_short_response(self) -> None:
        collector = SinaAuctionCollector({"source": "sina", "data_type": "auction"})
        short_payload = (
            "平安银行,0.000,10.450,0.000,0.000,0.000,0.000,0.000,"
            "0,0.000,0,0.000,0,0.000,0,0.000,0,0.000,0,0.000,"
            "0,0.000,0,0.000,0,0.000,0,0.000,0,0.000,"
            "2026-07-13,09:10:21,00"
        )
        mock_response = MagicMock()
        mock_response.text = f'var hq_str_sz000001="{short_payload}";'
        mock_get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient.get", mock_get):
            snapshot = await collector._fetch_snapshot("000001")

        assert snapshot["name"] == "平安银行"
        assert snapshot["current"] == "0.000"
        assert snapshot["buy_5_price"] == "0.000"
        mock_get.assert_awaited_once()


@pytest.mark.unit
class TestTushareIndexAuctionCollector:
    def _auction_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"ts_code": "600001.SH", "amount": 10e8},
                {"ts_code": "688001.SH", "amount": 3e8},
                {"ts_code": "688002.SH", "amount": 1e8},
                {"ts_code": "300001.SZ", "amount": 5e8},
                {"ts_code": "301001.SZ", "amount": 2e8},
                {"ts_code": "000001.SZ", "amount": 7e8},
            ]
        )

    def _cons_df(self) -> pd.DataFrame:
        return pd.DataFrame({"成分券代码": ["688001", "688002"]})

    def _collector(self) -> TushareIndexAuctionCollector:
        return TushareIndexAuctionCollector(
            {"source": "tushare", "data_type": "index-auction", "api_key": "token"}
        )

    @pytest.mark.asyncio
    async def test_collect_aggregates_by_index_universe(self) -> None:
        mock_pro = MagicMock()
        mock_pro.stk_auction.return_value = self._auction_df()
        with (
            patch("tushare.pro_api", return_value=mock_pro),
            patch(
                "akshare.index_stock_cons_csindex", return_value=self._cons_df()
            ),
        ):
            raw = await self._collector().collect(
                trade_date=datetime.date(2026, 7, 21)
            )

        mock_pro.stk_auction.assert_called_once_with(
            trade_date="20260721", offset=0, limit=8000
        )
        by_code = {item["index_code"]: item for item in raw}
        assert set(by_code) == {"sh000001", "sh000688", "sz399006"}
        # 上证指数 = 全部沪市 A 股（60/68）
        assert by_code["sh000001"]["auction_amount"] == pytest.approx(14e8)
        # 科创50 = 成分股合计
        assert by_code["sh000688"]["auction_amount"] == pytest.approx(4e8)
        # 创业板指 = 全部创业板（300/301），不含深市主板 000001
        assert by_code["sz399006"]["auction_amount"] == pytest.approx(7e8)
        assert all(item["trade_date"] == datetime.date(2026, 7, 21) for item in raw)
        assert all(item["source"] == "tushare" for item in raw)

    @pytest.mark.asyncio
    async def test_collect_paginates_when_full_page(self) -> None:
        """盘后全量超 8000 行时翻页拼齐，创业板不被截断。"""
        page_size = 8000
        page1 = pd.concat(
            [
                pd.DataFrame({"ts_code": ["600001.SH"], "amount": [10e8]}),
                pd.DataFrame(
                    {"ts_code": ["000001.SH"] * (page_size - 1), "amount": [1.0] * (page_size - 1)}
                ),
            ],
            ignore_index=True,
        )
        page2 = pd.DataFrame(
            [
                {"ts_code": "300001.SZ", "amount": 5e8},
                {"ts_code": "301001.SZ", "amount": 2e8},
            ]
        )
        mock_pro = MagicMock()
        mock_pro.stk_auction.side_effect = [page1, page2]
        with (
            patch("tushare.pro_api", return_value=mock_pro),
            patch("akshare.index_stock_cons_csindex", return_value=self._cons_df()),
        ):
            raw = await self._collector().collect(
                trade_date=datetime.date(2026, 7, 21)
            )

        assert mock_pro.stk_auction.call_count == 2
        mock_pro.stk_auction.assert_any_call(trade_date="20260721", offset=0, limit=page_size)
        mock_pro.stk_auction.assert_any_call(trade_date="20260721", offset=page_size, limit=page_size)
        by_code = {item["index_code"]: item for item in raw}
        # 创业板在第二页，翻页后聚合正确
        assert by_code["sz399006"]["auction_amount"] == pytest.approx(7e8)

    @pytest.mark.asyncio
    async def test_collect_respects_requested_symbols(self) -> None:
        mock_pro = MagicMock()
        mock_pro.stk_auction.return_value = self._auction_df()
        with patch("tushare.pro_api", return_value=mock_pro):
            raw = await self._collector().collect(
                symbols=["sh000001"], trade_date=datetime.date(2026, 7, 21)
            )

        assert [item["index_code"] for item in raw] == ["sh000001"]

    @pytest.mark.asyncio
    async def test_collect_empty_returns_empty(self) -> None:
        mock_pro = MagicMock()
        mock_pro.stk_auction.return_value = pd.DataFrame()
        with patch("tushare.pro_api", return_value=mock_pro):
            raw = await self._collector().collect(
                trade_date=datetime.date(2026, 7, 21)
            )
        assert raw == []

    @pytest.mark.asyncio
    async def test_collect_skips_empty_bucket(self) -> None:
        """早间深市数据滞后时，创业板/科创50 空桶不得写入 0 值。"""
        sh_only = pd.DataFrame(
            [
                {"ts_code": "600001.SH", "amount": 10e8},
                {"ts_code": "600002.SH", "amount": 2e8},
            ]
        )
        mock_pro = MagicMock()
        mock_pro.stk_auction.return_value = sh_only
        with (
            patch("tushare.pro_api", return_value=mock_pro),
            patch(
                "akshare.index_stock_cons_csindex", return_value=self._cons_df()
            ),
        ):
            raw = await self._collector().collect(
                trade_date=datetime.date(2026, 7, 21)
            )

        assert [item["index_code"] for item in raw] == ["sh000001"]
        assert raw[0]["auction_amount"] == pytest.approx(12e8)

    @pytest.mark.asyncio
    async def test_collect_skips_zero_sum_bucket(self) -> None:
        """桶内有行但合计为 0 视为数据异常，同样跳过留给重试。"""
        df = self._auction_df()
        df.loc[df["ts_code"].str[:3].isin(("300", "301", "302")), "amount"] = 0.0
        mock_pro = MagicMock()
        mock_pro.stk_auction.return_value = df
        with (
            patch("tushare.pro_api", return_value=mock_pro),
            patch(
                "akshare.index_stock_cons_csindex", return_value=self._cons_df()
            ),
        ):
            raw = await self._collector().collect(
                trade_date=datetime.date(2026, 7, 21)
            )

        codes = {item["index_code"] for item in raw}
        assert codes == {"sh000001", "sh000688"}

    @pytest.mark.asyncio
    async def test_collect_requires_api_key(self) -> None:
        collector = TushareIndexAuctionCollector(
            {"source": "tushare", "data_type": "index-auction"}
        )
        with pytest.raises(ValueError, match="api_key"):
            await collector.collect(trade_date=datetime.date(2026, 7, 21))
