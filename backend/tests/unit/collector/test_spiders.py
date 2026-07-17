import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from collector.spiders.cninfo_financial_report import CninfoFinancialReportCollector
from collector.spiders.cninfo_ipo import CninfoIpoCollector
from collector.spiders.eastmoney_financial_statement import (
    EastmoneyFinancialStatementCollector,
)
from collector.spiders.eastmoney_fund_flow import EastMoneyFundFlowCollector
from collector.spiders.eastmoney_fund_holdings import EastMoneyFundHoldingsCollector
from collector.spiders.sina_auction import SinaAuctionCollector
from collector.spiders.sina_kline import SinaKlineCollector
from collector.spiders.sina_news import SinaNewsCollector
from collector.spiders.sina_quote import SinaQuoteCollector
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
            "title": "2023年年度报告",
            "publish_date": datetime.date(2024, 3, 15),
            "report_type": "annual",
            "report_category": "年报",
            "source_url": "http://static.cninfo.com.cn/finalpage/2024-03-15/test.PDF",
            "announcement_id": "12345",
            "org_id": "org123",
            "file_bytes": b"PDF content",
            "file_size": 11,
            "file_type": "pdf",
            "source": "cninfo",
        }
        item = await collector.transform(raw)
        assert item["stock_code"] == "000001"
        assert item["report_type"] == "annual"
        assert await collector.validate(item) is True

    @pytest.mark.asyncio
    async def test_validate_rejects_missing_bytes(self) -> None:
        collector = CninfoFinancialReportCollector(
            {"source": "cninfo", "data_type": "financial_report"}
        )
        item = {
            "stock_code": "000001",
            "title": "2023年年度报告",
            "publish_date": datetime.date(2024, 3, 15),
            "source_url": "http://static.cninfo.com.cn/finalpage/2024-03-15/test.PDF",
            "file_bytes": b"",
        }
        assert await collector.validate(item) is False

    @pytest.mark.asyncio
    async def test_collect_downloads_pdfs(self) -> None:
        collector = CninfoFinancialReportCollector(
            {
                "source": "cninfo",
                "data_type": "financial_report",
                "max_pages": 1,
                "report_types": ["年报"],
            }
        )
        query_response = {
            "announcements": [
                {
                    "secCode": "000001",
                    "announcementTitle": "2023年年度报告",
                    "announcementTime": "2024-03-15",
                    "announcementId": "12345",
                    "orgId": "org123",
                    "adjunctUrl": "finalpage/2024-03-15/test.PDF",
                }
            ],
            "totalPages": 1,
        }
        pdf_bytes = b"%PDF-1.4 fake pdf"

        def _post(url: str, **kwargs: object) -> MagicMock:
            resp = MagicMock()
            if "topSearch" in url:
                resp.json.return_value = [{"code": "000001", "orgId": "org123"}]
            else:
                resp.json.return_value = query_response
            return resp

        pdf_response_mock = MagicMock()
        pdf_response_mock.content = pdf_bytes

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=_post)
        mock_client.get = AsyncMock(return_value=pdf_response_mock)

        with patch("httpx.AsyncClient", return_value=mock_client):
            raw = await collector.collect(symbols=["000001"])

        assert len(raw) == 1
        assert raw[0]["stock_code"] == "000001"
        assert raw[0]["file_bytes"] == pdf_bytes
        assert raw[0]["source_url"].endswith("test.PDF")

    @pytest.mark.asyncio
    async def test_store_uses_financial_report_store(self) -> None:
        collector = CninfoFinancialReportCollector(
            {"source": "cninfo", "data_type": "financial_report"}
        )
        items = [
            {
                "stock_code": "000001",
                "title": "2023年年度报告",
                "publish_date": datetime.date(2024, 3, 15),
                "report_type": "annual",
                "report_category": "年报",
                "source_url": "http://static.cninfo.com.cn/finalpage/2024-03-15/test.PDF",
                "announcement_id": "12345",
                "org_id": "org123",
                "file_bytes": b"PDF content",
                "file_size": 11,
                "file_type": "pdf",
                "source": "cninfo",
            }
        ]
        with patch(
            "collector.stores.financial_report_store.FinancialReportStore.save_many",
            AsyncMock(return_value=(1, [])),
        ):
            result = await collector.store(items)
        assert result == 1


@pytest.mark.unit
class TestEastmoneyFinancialStatementCollector:
    @pytest.mark.asyncio
    async def test_transform_and_validate(self) -> None:
        collector = EastmoneyFinancialStatementCollector(
            {"source": "eastmoney", "data_type": "financial_statement"}
        )
        raw = {
            "stock_code": "000001",
            "report_date": datetime.date(2024, 3, 31),
            "report_type": "q1",
            "balance": {
                "total_assets": Decimal("1000000"),
                "total_liabilities": Decimal("400000"),
                "total_equity": Decimal("600000"),
            },
            "income": {
                "total_revenue": Decimal("200000"),
                "operating_cost": Decimal("120000"),
                "net_profit": Decimal("50000"),
                "eps": Decimal("0.5"),
            },
            "cash": {
                "cf_operations": Decimal("30000"),
                "cf_investing": Decimal("-10000"),
                "cf_financing": Decimal("-5000"),
                "net_cash_flow": Decimal("15000"),
            },
        }
        item = await collector.transform(raw)
        assert item["stock_code"] == "000001"
        assert item["report_type"] == "q1"
        assert await collector.validate(item) is True

    @pytest.mark.asyncio
    async def test_validate_rejects_empty_sections(self) -> None:
        collector = EastmoneyFinancialStatementCollector(
            {"source": "eastmoney", "data_type": "financial_statement"}
        )
        item = {
            "stock_code": "000001",
            "report_date": datetime.date(2024, 3, 31),
            "report_type": "q1",
            "balance": {},
            "income": {},
            "cash": {},
        }
        assert await collector.validate(item) is False

    @pytest.mark.asyncio
    async def test_store_builds_table_rows(self) -> None:
        collector = EastmoneyFinancialStatementCollector(
            {"source": "eastmoney", "data_type": "financial_statement"}
        )
        items = [
            {
                "stock_code": "000001",
                "report_date": datetime.date(2024, 3, 31),
                "report_type": "q1",
                "balance": {
                    "total_assets": Decimal("1000000"),
                    "total_liabilities": Decimal("400000"),
                },
                "income": {
                    "total_revenue": Decimal("200000"),
                    "net_profit": Decimal("50000"),
                },
                "cash": {
                    "cf_operations": Decimal("30000"),
                },
            }
        ]
        collector.store = AsyncMock(return_value=3)  # type: ignore[method-assign]
        result = await collector.run(items=items)

        assert result.status.value == "success"
        assert result.items_stored == 3
        collector.store.assert_awaited_once()  # type: ignore[attr-defined]


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
class TestSinaQuoteCollector:
    @pytest.mark.asyncio
    async def test_transform_and_validate(self) -> None:
        collector = SinaQuoteCollector({"source": "sina", "data_type": "quote"})
        raw = {
            "stock_code": "000001",
            "stock_name": "平安银行",
            "price": 10.5,
            "change": 0.2,
            "pct_change": 1.94,
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
                "pct_change": 1.94,
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
        mock_redis.setex.assert_awaited_once()
        key, ttl, value = mock_redis.setex.await_args.args
        assert key == "quote:000001"
        assert ttl == 60
        assert "000001" in value


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
