import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from collector.spiders.cninfo_financial_report import CninfoFinancialReportCollector
from collector.spiders.cninfo_ipo import CninfoIpoCollector
from collector.spiders.eastmoney_fund_flow import EastMoneyFundFlowCollector
from collector.spiders.eastmoney_fund_holdings import EastMoneyFundHoldingsCollector
from collector.spiders.sina_auction import SinaAuctionCollector
from collector.spiders.sina_kline import SinaKlineCollector
from collector.spiders.sina_news import SinaNewsCollector
from collector.spiders.ths_auction import ThsAuctionCollector
from collector.spiders.ths_kline import ThsKlineCollector


@pytest.mark.unit
class TestCninfoFinancialReportCollector:
    @pytest.mark.asyncio
    async def test_transform_and_validate(self) -> None:
        collector = CninfoFinancialReportCollector(
            {"source": "cninfo", "data_type": "financial_report"}
        )
        raw = {
            "stock_code": "000001",
            "doc_type": "financial_report",
            "title": "2023年年度报告",
            "summary": None,
            "content": None,
            "source": "cninfo",
            "source_url": "http://www.cninfo.com.cn/new/disclosure/detail?stockCode=000001",
            "publish_date": datetime.datetime(2024, 3, 15, 0, 0, 0),
            "sentiment": None,
            "keywords": None,
            "industry_tags": None,
            "es_id": None,
            "extra": '{"category": "年报", "pdf_url": "http://www.cninfo.com.cn/new/disclosure/detail?stockCode=000001"}',
        }
        item = await collector.transform(raw)
        assert item["stock_code"] == "000001"
        assert item["doc_type"] == "financial_report"
        assert await collector.validate(item) is True

    @pytest.mark.asyncio
    async def test_validate_rejects_missing_title(self) -> None:
        collector = CninfoFinancialReportCollector(
            {"source": "cninfo", "data_type": "financial_report"}
        )
        item = {
            "stock_code": "000001",
            "publish_date": datetime.datetime(2024, 3, 15, 0, 0, 0),
        }
        assert await collector.validate(item) is False


@pytest.mark.unit
class TestThsKlineCollector:
    @pytest.mark.asyncio
    async def test_transform_and_validate(self) -> None:
        collector = ThsKlineCollector({"source": "ths", "data_type": "kline_daily"})
        raw = {
            "stock_code": "000001",
            "trade_date": "2024-01-02",
            "open": 10.5,
            "high": 11.0,
            "low": 10.2,
            "close": 10.8,
            "volume": 100000,
            "amount": 1080000.0,
            "amplitude": 7.62,
            "pct_change": 2.86,
            "turnover_rate": 0.52,
        }
        item = await collector.transform(raw)
        assert item["close"] == 10.8
        assert item["volume"] == 100000
        assert await collector.validate(item) is True

    @pytest.mark.asyncio
    async def test_validate_rejects_missing_close(self) -> None:
        collector = ThsKlineCollector({"source": "ths", "data_type": "kline_daily"})
        item = {"stock_code": "000001", "trade_date": "2024-01-02", "close": None}
        assert await collector.validate(item) is False


@pytest.mark.unit
class TestSinaKlineCollector:
    @pytest.mark.asyncio
    async def test_transform_and_validate(self) -> None:
        collector = SinaKlineCollector({"source": "sina", "data_type": "kline_daily"})
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
            "pct_change": None,
            "turnover_rate": 0.52,
        }
        item = await collector.transform(raw)
        assert item["close"] == 10.8
        assert item["volume"] == 100000
        assert await collector.validate(item) is True


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
class TestCninfoIpoCollector:
    @pytest.mark.asyncio
    async def test_transform_and_validate(self) -> None:
        collector = CninfoIpoCollector({"source": "cninfo", "data_type": "ipo_info"})
        raw = {
            "stock_code": "001387",
            "stock_name": "Test IPO",
            "listing_date": datetime.date(2024, 1, 15),
            "subscription_date": datetime.date(2024, 1, 5),
            "issue_price": 10.0,
            "total_issue_quantity": 5000000.0,
            "issue_pe_ratio": 22.5,
            "online_winning_rate": 0.03,
            "lottery_result_date": datetime.date(2024, 1, 8),
            "winning_announcement_date": datetime.date(2024, 1, 9),
            "payment_date": datetime.date(2024, 1, 10),
            "online_subscription_limit": 10000.0,
            "online_issue_quantity": 4500000.0,
        }
        item = await collector.transform(raw)
        assert item["stock_code"] == "001387"
        assert item["subscription_date"] == datetime.date(2024, 1, 5)
        assert item["source"] == "cninfo"
        assert await collector.validate(item) is True

    @pytest.mark.asyncio
    async def test_validate_rejects_missing_subscription_date(self) -> None:
        collector = CninfoIpoCollector({"source": "cninfo", "data_type": "ipo_info"})
        item = {"stock_code": "001387"}
        assert await collector.validate(item) is False


@pytest.mark.unit
class TestEastMoneyFundHoldingsCollector:
    @pytest.mark.asyncio
    async def test_transform_and_validate(self) -> None:
        collector = EastMoneyFundHoldingsCollector(
            {"source": "eastmoney", "data_type": "fund_holdings"}
        )
        raw = {
            "stock_code": "000001",
            "stock_name": "平安银行",
            "report_date": datetime.date(2025, 3, 31),
            "holding_fund_count": 100,
            "total_holding_quantity": 5000000,
            "holding_market_value": 50000000.0,
            "holding_change": "增持",
            "holding_change_quantity": 100000,
            "holding_change_ratio": 0.02,
        }
        item = await collector.transform(raw)
        assert item["stock_code"] == "000001"
        assert item["report_date"] == datetime.date(2025, 3, 31)
        assert item["source"] == "eastmoney"
        assert await collector.validate(item) is True

    @pytest.mark.asyncio
    async def test_validate_rejects_missing_report_date(self) -> None:
        collector = EastMoneyFundHoldingsCollector(
            {"source": "eastmoney", "data_type": "fund_holdings"}
        )
        item = {"stock_code": "000001"}
        assert await collector.validate(item) is False


@pytest.mark.unit
class TestEastMoneyFundFlowCollector:
    @pytest.mark.asyncio
    async def test_transform_and_validate(self) -> None:
        collector = EastMoneyFundFlowCollector({"source": "eastmoney", "data_type": "fund_flow"})
        raw = {
            "stock_code": "000001",
            "trade_date": datetime.date(2024, 1, 2),
            "main_net_inflow": 1_000_000.0,
            "super_large_net": 500_000.0,
            "large_net": 500_000.0,
            "medium_net": -300_000.0,
            "small_net": -700_000.0,
        }
        item = await collector.transform(raw)
        assert item["main_net_inflow"] == 1_000_000.0
        assert item["small_net"] == -700_000.0
        assert await collector.validate(item) is True


@pytest.mark.unit
class TestSinaNewsCollector:
    @pytest.mark.asyncio
    async def test_transform_and_validate(self) -> None:
        collector = SinaNewsCollector({"source": "sina", "data_type": "news"})
        raw = {
            "stock_code": "000001",
            "doc_type": "news",
            "title": "Test title",
            "summary": "Test summary",
            "content": "Test content",
            "source": "EastMoney",
            "source_url": "http://example.com/news/1",
            "publish_date": "2024-01-02 10:00:00",
        }
        item = await collector.transform(raw)
        assert item["title"] == "Test title"
        assert item["publish_date"] == datetime.datetime(2024, 1, 2, 10, 0, 0)
        assert await collector.validate(item) is True

    @pytest.mark.asyncio
    async def test_validate_rejects_empty_title(self) -> None:
        collector = SinaNewsCollector({"source": "sina", "data_type": "news"})
        item = {
            "stock_code": "000001",
            "title": "",
            "source_url": "http://example.com/news/1",
            "publish_date": datetime.datetime(2024, 1, 2, 10, 0, 0),
        }
        assert await collector.validate(item) is False


@pytest.mark.unit
class TestCollectorRun:
    @pytest.mark.asyncio
    async def test_kline_run_with_mocked_collect(self) -> None:
        collector = SinaKlineCollector({"source": "sina", "data_type": "kline_daily"})
        collector.store = AsyncMock(return_value=1)  # type: ignore[method-assign]
        collector.collect = AsyncMock(  # type: ignore[method-assign]
            return_value=[
                {
                    "stock_code": "000001",
                    "trade_date": "2024-01-02",
                    "open": 10.5,
                    "high": 11.0,
                    "low": 10.2,
                    "close": 10.8,
                    "volume": 100000,
                    "amount": 1080000.0,
                    "amplitude": None,
                    "pct_change": None,
                    "turnover_rate": 0.52,
                }
            ]
        )

        result = await collector.run()

        assert result.status.value == "success"
        assert result.items_collected == 1
        assert result.items_stored == 1
        collector.store.assert_awaited_once()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_fund_flow_run_with_mocked_akshare(self) -> None:
        collector = EastMoneyFundFlowCollector({"source": "eastmoney", "data_type": "fund_flow"})
        mock_df = pd.DataFrame(
            [
                {
                    "股票代码": 1,
                    "股票简称": "Test",
                    "最新价": 10.0,
                    "涨跌幅": 1.0,
                    "换手率": 1.0,
                    "流入资金": "100万",
                    "流出资金": "50万",
                    "净额": "50万",
                    "成交额": "150万",
                }
            ]
        )

        with patch("akshare.stock_fund_flow_individual", return_value=mock_df):
            collector.store = AsyncMock(return_value=1)  # type: ignore[method-assign]
            result = await collector.run(symbols=["000001"])

        assert result.status.value == "success"
        assert result.items_collected == 1
        assert result.items_stored == 1
