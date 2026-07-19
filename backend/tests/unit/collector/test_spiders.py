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
from collector.spiders.eastmoney_limit_up_pool import EastMoneyLimitUpPoolCollector
from collector.spiders.eastmoney_sector_fund_flow import (
    EastMoneySectorFundFlowCollector,
)
from collector.spiders.sina_auction import SinaAuctionCollector
from collector.spiders.sina_kline import SinaKlineCollector
from collector.spiders.sina_news import SinaNewsCollector
from collector.spiders.sina_quote import SinaQuoteCollector
from collector.spiders.sina_stock_list import SinaStockListCollector
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




def _sw_info(rows: list[dict[str, str]]) -> pd.DataFrame:
    return pd.DataFrame(rows)


@pytest.mark.unit
class TestSinaStockListCollector:
    @pytest.mark.asyncio
    async def test_transform_and_validate(self) -> None:
        collector = SinaStockListCollector(
            {"source": "sina", "data_type": "stock_list"}
        )
        raw = {
            "stock_code": "600000",
            "stock_name": "浦发银行",
            "market": "sh",
            "full_name": "上海浦东发展银行股份有限公司",
            "industry_l1": "银行",
            "industry_l2": "全国性银行",
            "industry_l3": "股份制银行",
            "listing_date": datetime.date(1999, 11, 10),
            "total_shares": 29352080397,
            "circulating_shares": 29352080397,
            "province": None,
        }
        item = await collector.transform(raw)
        assert item["stock_code"] == "600000"
        assert item["industry_l1"] == "银行"
        assert item["total_shares"] == 29352080397
        assert await collector.validate(item) is True

    @pytest.mark.asyncio
    async def test_validate_rejects_missing_name(self) -> None:
        collector = SinaStockListCollector(
            {"source": "sina", "data_type": "stock_list"}
        )
        item = {"stock_code": "000001", "stock_name": "", "market": "sz"}
        assert await collector.validate(item) is False

    def _patch_akshare(self, components: dict[str, list[str]]):
        base_df = pd.DataFrame(
            [
                {"code": "000001", "name": "平安银行"},
                {"code": "600000", "name": "浦发银行"},
                {"code": "920001", "name": "纬达光电"},
            ]
        )
        sh_df = pd.DataFrame(
            [
                {
                    "证券代码": "600000",
                    "公司全称": "上海浦东发展银行股份有限公司",
                    "上市日期": "1999-11-10",
                }
            ]
        )
        sz_df = pd.DataFrame(
            [
                {
                    "A股代码": "000001",
                    "A股上市日期": "1991-04-03",
                    "A股总股本": "19,405,918,198",
                    "A股流通股本": "19,405,684,991",
                }
            ]
        )
        bj_df = pd.DataFrame(
            [
                {
                    "证券代码": "920001",
                    "总股本": 153656204,
                    "流通股本": 88691020,
                    "上市日期": "2022-12-27",
                    "地区": "江苏省",
                }
            ]
        )
        l1_df = _sw_info([{"行业代码": "801780.SI", "行业名称": "银行"}])
        l2_df = _sw_info(
            [{"行业代码": "801781.SI", "行业名称": "全国性银行", "上级行业": "银行"}]
        )
        l3_df = _sw_info(
            [
                {
                    "行业代码": "859781.SI",
                    "行业名称": "股份制银行",
                    "上级行业": "全国性银行",
                }
            ]
        )

        def _components(symbol: str) -> pd.DataFrame:
            return pd.DataFrame(
                {"证券代码": components.get(symbol, [])}
            )

        return (
            patch("akshare.stock_info_a_code_name", return_value=base_df),
            patch("akshare.stock_info_sh_name_code", return_value=sh_df),
            patch("akshare.stock_info_sz_name_code", return_value=sz_df),
            patch("akshare.stock_info_bj_name_code", return_value=bj_df),
            patch("akshare.sw_index_first_info", return_value=l1_df),
            patch("akshare.sw_index_second_info", return_value=l2_df),
            patch("akshare.sw_index_third_info", return_value=l3_df),
            patch("akshare.index_component_sw", side_effect=_components),
        )

    @pytest.mark.asyncio
    async def test_collect_merges_exchange_details_and_sw_industry(self) -> None:
        collector = SinaStockListCollector(
            {"source": "sina", "data_type": "stock_list", "sw_request_delay": 0}
        )
        components = {"859781": ["000001", "600000"], "801780": ["920001"]}
        patches = self._patch_akshare(components)

        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7]:
            raw = await collector.collect()

        assert len(raw) == 3
        by_code = {item["stock_code"]: item for item in raw}

        sz = by_code["000001"]
        assert sz["market"] == "sz"
        assert sz["listing_date"] == datetime.date(1991, 4, 3)
        assert sz["total_shares"] == 19405918198
        assert sz["circulating_shares"] == 19405684991
        assert sz["industry_l1"] == "银行"
        assert sz["industry_l2"] == "全国性银行"
        assert sz["industry_l3"] == "股份制银行"

        sh = by_code["600000"]
        assert sh["market"] == "sh"
        assert sh["full_name"] == "上海浦东发展银行股份有限公司"
        assert sh["industry_l3"] == "股份制银行"

        bj = by_code["920001"]
        assert bj["market"] == "bj"
        assert bj["province"] == "江苏省"
        # 920001 只在 L1 指数中，回退到一级行业
        assert bj["industry_l1"] == "银行"
        assert bj["industry_l2"] is None
        assert bj["industry_l3"] is None

    @pytest.mark.asyncio
    async def test_collect_tolerates_source_failures(self) -> None:
        collector = SinaStockListCollector(
            {"source": "sina", "data_type": "stock_list", "sw_request_delay": 0}
        )
        base_df = pd.DataFrame([{"code": "000001", "name": "平安银行"}])

        with (
            patch("akshare.stock_info_a_code_name", return_value=base_df),
            patch("akshare.stock_info_sh_name_code", side_effect=RuntimeError("boom")),
            patch("akshare.stock_info_sz_name_code", side_effect=RuntimeError("boom")),
            patch("akshare.stock_info_bj_name_code", side_effect=RuntimeError("boom")),
            patch("akshare.sw_index_first_info", side_effect=RuntimeError("boom")),
        ):
            raw = await collector.collect()

        assert len(raw) == 1
        assert raw[0]["stock_code"] == "000001"
        assert raw[0]["market"] == "sz"

    @pytest.mark.asyncio
    async def test_collect_with_requested_symbols(self) -> None:
        collector = SinaStockListCollector(
            {"source": "sina", "data_type": "stock_list", "sw_request_delay": 0}
        )
        patches = self._patch_akshare({"859781": ["600000"]})

        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7]:
            raw = await collector.collect(symbols=["600000"])

        assert len(raw) == 1
        assert raw[0]["stock_code"] == "600000"
        assert raw[0]["industry_l1"] == "银行"


@pytest.mark.unit
class TestEastMoneyLimitUpPoolCollector:
    @pytest.mark.asyncio
    async def test_collect_maps_akshare_columns(self) -> None:
        df = pd.DataFrame(
            [
                {
                    "序号": 1,
                    "代码": "002338",
                    "名称": "奥普光电",
                    "涨跌幅": 10.01,
                    "最新价": 25.6,
                    "成交额": 3.5e8,
                    "流通市值": 1.2e10,
                    "总市值": 1.3e10,
                    "换手率": 9.8,
                    "封板资金": 4.2e8,
                    "首次封板时间": "092500",
                    "最后封板时间": "135900",
                    "炸板次数": 2,
                    "涨停统计": "6/6",
                    "连板数": 6,
                    "所属行业": "光学光电子",
                }
            ]
        )
        collector = EastMoneyLimitUpPoolCollector(
            {"source": "eastmoney", "data_type": "limit_up_pool"}
        )
        with patch("akshare.stock_zt_pool_em", return_value=df):
            raw = await collector.collect(trade_date=datetime.date(2026, 7, 17))

        assert len(raw) == 1
        assert raw[0]["stock_code"] == "002338"
        assert raw[0]["consecutive_boards"] == 6
        assert raw[0]["sealed_amount"] == 4.2e8
        assert raw[0]["industry"] == "光学光电子"

    @pytest.mark.asyncio
    async def test_collect_empty_pool(self) -> None:
        collector = EastMoneyLimitUpPoolCollector(
            {"source": "eastmoney", "data_type": "limit_up_pool"}
        )
        with patch("akshare.stock_zt_pool_em", return_value=pd.DataFrame()):
            raw = await collector.collect(trade_date=datetime.date(2026, 7, 17))

        assert raw == []

    @pytest.mark.asyncio
    async def test_transform_and_validate(self) -> None:
        collector = EastMoneyLimitUpPoolCollector(
            {"source": "eastmoney", "data_type": "limit_up_pool"}
        )
        raw = {
            "trade_date": datetime.date(2026, 7, 17),
            "stock_code": "002338",
            "stock_name": "奥普光电",
            "change_pct": 10.01,
            "latest_price": 25.6,
            "turnover_rate": 9.8,
            "sealed_amount": 4.2e8,
            "first_seal_time": "092500",
            "last_seal_time": "135900",
            "break_count": 2,
            "limit_stat": "6/6",
            "consecutive_boards": 6,
            "industry": "光学光电子",
        }
        item = await collector.transform(raw)
        assert item["source"] == "eastmoney"
        assert item["consecutive_boards"] == 6
        assert await collector.validate(item) is True

    @pytest.mark.asyncio
    async def test_validate_rejects_missing_code(self) -> None:
        collector = EastMoneyLimitUpPoolCollector(
            {"source": "eastmoney", "data_type": "limit_up_pool"}
        )
        assert await collector.validate(
            {"trade_date": datetime.date(2026, 7, 17), "stock_code": None}
        ) is False


@pytest.mark.unit
class TestEastMoneySectorFundFlowCollector:
    @pytest.mark.asyncio
    async def test_collect_maps_push2_fields(self) -> None:
        rows = [
            {
                "f12": "BK1036",
                "f14": "半导体",
                "f3": 4.2,
                "f62": 2.26e9,
                "f66": 1.5e9,
                "f72": 7.6e8,
                "f78": -3e8,
                "f84": -1.9e9,
                "f204": "北方华创",
                "f205": "002371",
            }
        ]
        collector = EastMoneySectorFundFlowCollector(
            {"source": "eastmoney", "data_type": "sector_fund_flow"}
        )
        with patch.object(collector, "_fetch_rank", return_value=rows):
            raw = await collector.collect(sector_type="industry")

        assert len(raw) == 1
        assert raw[0]["sector_name"] == "半导体"
        assert raw[0]["sector_code"] == "BK1036"
        assert raw[0]["change_pct"] == 4.2
        assert raw[0]["main_net_inflow"] == 2.26e9
        assert raw[0]["top_stock_name"] == "北方华创"
        assert raw[0]["top_stock_code"] == "002371"

        item = await collector.transform(raw[0])
        assert item["change_pct"] == 4.2
        assert await collector.validate(item) is True

    def test_fetch_rank_paginates(self) -> None:
        collector = EastMoneySectorFundFlowCollector(
            {"source": "eastmoney", "data_type": "sector_fund_flow"}
        )
        pages = [
            {"total": 3, "diff": [{"f14": "板块A"}, {"f14": "板块B"}]},
            {"total": 3, "diff": [{"f14": "板块C"}]},
        ]
        with (
            patch(
                "collector.spiders.eastmoney_sector_fund_flow._PAGE_SIZE", 2
            ),
            patch.object(
                collector, "_request_page", side_effect=pages
            ) as request_page,
        ):
            rows = collector._fetch_rank("industry")

        assert [row["f14"] for row in rows] == ["板块A", "板块B", "板块C"]
        assert request_page.call_count == 2
        assert request_page.call_args_list[1].args[0]["pn"] == 2

    def test_request_page_uses_shared_eastmoney_client(self) -> None:
        collector = EastMoneySectorFundFlowCollector(
            {"source": "eastmoney", "data_type": "sector_fund_flow"}
        )
        response = MagicMock()
        response.json.return_value = {"data": {"total": 0, "diff": []}}
        with patch(
            "collector.spiders.eastmoney_sector_fund_flow.eastmoney_get",
            return_value=response,
        ) as get:
            data = collector._request_page({"pn": 1})

        assert data == {"total": 0, "diff": []}
        assert get.call_args.args[0] == "https://push2.eastmoney.com/api/qt/clist/get"
        assert get.call_args.kwargs["params"] == {"pn": 1}


@pytest.mark.unit
class TestThsSectorFundFlowCollector:
    def _make_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "序号": 1,
                    "行业": "酿酒行业",
                    "行业指数": 3800.5,
                    "行业-涨跌幅": 1.23,
                    "流入资金": "10.5亿",
                    "流出资金": "9.5亿",
                    "净额": "1.23亿",
                    "公司家数": 37,
                    "领涨股": "贵州茅台",
                    "领涨股-涨跌幅": 2.5,
                    "当前价": 1680.0,
                },
                {
                    "序号": 2,
                    "行业": "银行",
                    "行业指数": 3200.0,
                    "行业-涨跌幅": -0.5,
                    "流入资金": "5000万",
                    "流出资金": "6000万",
                    "净额": -3.15,
                    "公司家数": 42,
                    "领涨股": "招商银行",
                    "领涨股-涨跌幅": 0.8,
                    "当前价": 35.0,
                },
            ]
        )

    @pytest.mark.asyncio
    async def test_collect_maps_ths_fields(self) -> None:
        from collector.spiders.ths_sector_fund_flow import ThsSectorFundFlowCollector

        collector = ThsSectorFundFlowCollector(
            {"source": "ths", "data_type": "sector_fund_flow"}
        )
        with patch(
            "akshare.stock_fund_flow_industry", return_value=self._make_df()
        ):
            raw = await collector.collect(sector_type="industry")

        assert len(raw) == 2
        first = raw[0]
        assert first["sector_code"] == "酿酒行业"
        assert first["sector_name"] == "酿酒行业"
        assert first["sector_type"] == "industry"
        assert first["change_pct"] == 1.23
        assert first["main_net_inflow"] == 1.23 * 100_000_000
        assert first["super_large_net"] is None
        assert first["top_stock_name"] == "贵州茅台"
        assert raw[1]["main_net_inflow"] == -3.15 * 100_000_000

    @pytest.mark.asyncio
    async def test_collect_rejects_non_industry(self) -> None:
        from collector.spiders.ths_sector_fund_flow import ThsSectorFundFlowCollector

        collector = ThsSectorFundFlowCollector(
            {"source": "ths", "data_type": "sector_fund_flow"}
        )
        with pytest.raises(ValueError, match="仅支持行业板块"):
            await collector.collect(sector_type="concept")

    @pytest.mark.asyncio
    async def test_validate(self) -> None:
        from collector.spiders.ths_sector_fund_flow import ThsSectorFundFlowCollector

        collector = ThsSectorFundFlowCollector(
            {"source": "ths", "data_type": "sector_fund_flow"}
        )
        item = {
            "sector_code": "酿酒行业",
            "sector_name": "酿酒行业",
            "trade_date": datetime.date.today(),
        }
        assert await collector.validate(item) is True
        assert await collector.validate({**item, "sector_name": None}) is False
