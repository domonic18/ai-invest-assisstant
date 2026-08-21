import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from collector.spiders.cninfo_financial_report import CninfoFinancialReportCollector
from collector.spiders.cninfo_ipo import CninfoIpoCollector
from collector.spiders.eastmoney_a50_kline import EastmoneyA50KlineCollector
from collector.spiders.eastmoney_broken_pool import EastmoneyBrokenPoolCollector
from collector.spiders.eastmoney_financial_statement import (
    EastmoneyFinancialStatementCollector,
)
from collector.spiders.eastmoney_fund_flow import EastMoneyFundFlowCollector
from collector.spiders.eastmoney_fund_holdings import EastMoneyFundHoldingsCollector
from collector.spiders.eastmoney_limit_down_pool import (
    EastmoneyLimitDownPoolCollector,
)
from collector.spiders.eastmoney_limit_up_pool import EastMoneyLimitUpPoolCollector
from collector.spiders.eastmoney_sector_fund_flow import (
    EastMoneySectorFundFlowCollector,
)
from collector.spiders.exchange_market_amount import ExchangeMarketAmountCollector
from collector.spiders.sina_auction import SinaAuctionCollector
from collector.spiders.sina_etf_kline import SinaEtfKlineCollector
from collector.spiders.sina_index_kline import SinaIndexKlineCollector
from collector.spiders.sina_index_minute import SinaIndexMinuteCollector
from collector.spiders.sina_index_spot import SinaIndexSpotCollector
from collector.spiders.sina_kline import SinaKlineCollector
from collector.spiders.sina_market_breadth import (
    SinaMarketBreadthCollector,
    count_breadth,
)
from collector.spiders.sina_news import SinaNewsCollector
from collector.spiders.sina_quote import SinaQuoteCollector
from collector.spiders.sina_stock_list import SinaStockListCollector
from collector.spiders.sina_stock_minute import SinaStockMinuteCollector
from collector.spiders.ths_auction import ThsAuctionCollector
from collector.spiders.ths_kline import ThsKlineCollector
from collector.spiders.tushare_index_auction import TushareIndexAuctionCollector


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

    def test_report_types_accepts_english_enums(self) -> None:
        collector = CninfoFinancialReportCollector(
            {
                "source": "cninfo",
                "data_type": "financial_report",
                "report_types": ["annual", "semi_annual", "q1", "q3"],
            }
        )
        assert collector.report_types == ["年报", "半年报", "一季报", "三季报"]

    @pytest.mark.asyncio
    async def test_collect_downloads_pdfs(self) -> None:
        collector = CninfoFinancialReportCollector(
            {
                "source": "cninfo",
                "data_type": "financial_report",
                "max_pages": 1,
                "report_types": ["annual"],
            }
        )
        assert collector.report_types == ["年报"]
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
                "cash_flow_from_operations": Decimal("30000"),
                "cash_flow_from_investing": Decimal("-10000"),
                "cash_flow_from_financing": Decimal("-5000"),
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
                    "cash_flow_from_operations": Decimal("30000"),
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
        collector = ThsKlineCollector({"source": "ths", "data_type": "quote_kline_stock_daily"})
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
            "change_pct": 2.86,
            "turnover_rate": 0.52,
        }
        item = await collector.transform(raw)
        assert item["close"] == 10.8
        assert item["volume"] == 100000
        assert await collector.validate(item) is True

    @pytest.mark.asyncio
    async def test_validate_rejects_missing_close(self) -> None:
        collector = ThsKlineCollector({"source": "ths", "data_type": "quote_kline_stock_daily"})
        item = {"stock_code": "000001", "trade_date": "2024-01-02", "close": None}
        assert await collector.validate(item) is False


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
        with patch(
            "akshare.stock_zh_index_daily", return_value=mock_df
        ) as mock_fetch:
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
        with patch("akshare.fund_etf_hist_sina", return_value=mock_df) as mock_fetch:
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
        with patch("akshare.fund_etf_hist_sina", return_value=pd.DataFrame()):
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
            {"source": "eastmoney", "data_type": "fund_holding"}
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
            {"source": "eastmoney", "data_type": "fund_holding"}
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
        mock_redis.setex.assert_awaited_once()
        key, ttl, value = mock_redis.setex.await_args.args
        assert key == "quote:000001"
        assert ttl == 60
        assert "000001" in value


@pytest.mark.unit
class TestCollectorRun:
    @pytest.mark.asyncio
    async def test_kline_run_with_mocked_collect(self) -> None:
        collector = SinaKlineCollector({"source": "sina", "data_type": "quote_kline_stock_daily"})
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
                    "change_pct": None,
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
            "industry_level_1": "银行",
            "industry_level_2": "全国性银行",
            "industry_level_3": "股份制银行",
            "listing_date": datetime.date(1999, 11, 10),
            "total_shares": 29352080397,
            "circulating_shares": 29352080397,
            "province": None,
        }
        item = await collector.transform(raw)
        assert item["stock_code"] == "600000"
        assert item["industry_level_1"] == "银行"
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
        assert sz["industry_level_1"] == "银行"
        assert sz["industry_level_2"] == "全国性银行"
        assert sz["industry_level_3"] == "股份制银行"

        sh = by_code["600000"]
        assert sh["market"] == "sh"
        assert sh["full_name"] == "上海浦东发展银行股份有限公司"
        assert sh["industry_level_3"] == "股份制银行"

        bj = by_code["920001"]
        assert bj["market"] == "bj"
        assert bj["province"] == "江苏省"
        # 920001 只在 L1 指数中，回退到一级行业
        assert bj["industry_level_1"] == "银行"
        assert bj["industry_level_2"] is None
        assert bj["industry_level_3"] is None

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
        assert raw[0]["industry_level_1"] == "银行"


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
            {"source": "eastmoney", "data_type": "pool_limit_up_stock"}
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
            {"source": "eastmoney", "data_type": "pool_limit_up_stock"}
        )
        with patch("akshare.stock_zt_pool_em", return_value=pd.DataFrame()):
            raw = await collector.collect(trade_date=datetime.date(2026, 7, 17))

        assert raw == []

    @pytest.mark.asyncio
    async def test_transform_and_validate(self) -> None:
        collector = EastMoneyLimitUpPoolCollector(
            {"source": "eastmoney", "data_type": "pool_limit_up_stock"}
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
            "broken_limit_count": 2,
            "limit_status": "6/6",
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
            {"source": "eastmoney", "data_type": "pool_limit_up_stock"}
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
            {"source": "eastmoney", "data_type": "capital_fund_flow_sector"}
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
            {"source": "eastmoney", "data_type": "capital_fund_flow_sector"}
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

    @pytest.mark.asyncio
    async def test_collect_history_picks_target_date_row(self) -> None:
        collector = EastMoneySectorFundFlowCollector(
            {"source": "eastmoney", "data_type": "capital_fund_flow_sector"}
        )
        boards = [{"f12": "BK0420", "f14": "航空机场"}]
        klines = [
            "2026-07-16,100.0,10.0,20.0,30.0,40.0,1.5",
            "2026-07-17,-162370288.0,292831632.0,-130461344.0,-133406864.0,-28963424.0,-0.88",
        ]
        with (
            patch.object(collector, "_fetch_rank", return_value=boards),
            patch.object(collector, "_fetch_daykline", return_value=klines),
        ):
            raw = await collector.collect(
                sector_type="industry", trade_date=datetime.date(2026, 7, 17)
            )

        assert len(raw) == 1
        item = raw[0]
        assert item["sector_code"] == "BK0420"
        assert item["trade_date"] == datetime.date(2026, 7, 17)
        assert item["main_net_inflow"] == -162370288.0
        assert item["small_net"] == 292831632.0
        assert item["medium_net"] == -130461344.0
        assert item["large_net"] == -133406864.0
        assert item["super_large_net"] == -28963424.0
        assert item["change_pct"] == -0.88
        assert item["top_stock_name"] is None
        assert await collector.validate(await collector.transform(item)) is True

    @pytest.mark.asyncio
    async def test_collect_history_skips_non_trading_day(self) -> None:
        collector = EastMoneySectorFundFlowCollector(
            {"source": "eastmoney", "data_type": "capital_fund_flow_sector"}
        )
        with (
            patch(
                "collector.spiders.eastmoney_sector_fund_flow.is_trading_day",
                return_value=False,
            ),
            patch.object(
                collector, "_fetch_rank", side_effect=AssertionError("不应请求网络")
            ),
        ):
            raw = await collector.collect(
                sector_type="industry", trade_date=datetime.date(2026, 7, 19)
            )

        assert raw == []

    def test_request_page_uses_shared_eastmoney_client(self) -> None:
        collector = EastMoneySectorFundFlowCollector(
            {"source": "eastmoney", "data_type": "capital_fund_flow_sector"}
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
            {"source": "ths", "data_type": "capital_fund_flow_sector"}
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
    async def test_collect_concept_maps_ths_fields(self) -> None:
        from collector.spiders.ths_sector_fund_flow import ThsSectorFundFlowCollector

        collector = ThsSectorFundFlowCollector(
            {"source": "ths", "data_type": "capital_fund_flow_sector"}
        )
        with patch(
            "akshare.stock_fund_flow_concept", return_value=self._make_df()
        ):
            raw = await collector.collect(sector_type="concept")

        assert len(raw) == 2
        first = raw[0]
        assert first["sector_code"] == "酿酒行业"
        assert first["sector_name"] == "酿酒行业"
        assert first["sector_type"] == "concept"
        assert first["change_pct"] == 1.23
        assert first["main_net_inflow"] == 1.23 * 100_000_000
        assert first["top_stock_name"] == "贵州茅台"

    @pytest.mark.asyncio
    async def test_collect_rejects_unsupported_sector_type(self) -> None:
        from collector.spiders.ths_sector_fund_flow import ThsSectorFundFlowCollector

        collector = ThsSectorFundFlowCollector(
            {"source": "ths", "data_type": "capital_fund_flow_sector"}
        )
        with pytest.raises(ValueError, match="仅支持行业/概念板块"):
            await collector.collect(sector_type="region")

    @pytest.mark.asyncio
    async def test_validate(self) -> None:
        from collector.spiders.ths_sector_fund_flow import ThsSectorFundFlowCollector

        collector = ThsSectorFundFlowCollector(
            {"source": "ths", "data_type": "capital_fund_flow_sector"}
        )
        item = {
            "sector_code": "酿酒行业",
            "sector_name": "酿酒行业",
            "trade_date": datetime.date.today(),
        }
        assert await collector.validate(item) is True
        assert await collector.validate({**item, "sector_name": None}) is False


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
            raw = await collector.collect(trade_date=datetime.date.today())

        assert len(raw) == 1
        item = raw[0]
        assert item["trade_date"] == datetime.date.today()
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
                "collector.spiders.sina_stock_minute._fetch_limit_up_codes",
                AsyncMock(return_value=["600001"]),
            ),
            patch("akshare.stock_zh_a_minute", return_value=self._df()),
        ):
            raw = await collector.collect(trade_date=datetime.date(2026, 7, 21))

        assert {item["stock_code"] for item in raw} == {"600001"}


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


@pytest.mark.unit
class TestEastmoneyBrokenPoolCollector:
    @pytest.mark.asyncio
    async def test_collect_counts_broken_pool(self) -> None:
        collector = EastmoneyBrokenPoolCollector(
            {"source": "eastmoney", "data_type": "broken-pool"}
        )
        mock_df = pd.DataFrame({"代码": ["000001", "000002", "000003"]})
        with patch("akshare.stock_zt_pool_zbgc_em", return_value=mock_df):
            raw = await collector.collect(trade_date=datetime.date(2026, 7, 17))

        assert raw == [
            {"trade_date": datetime.date(2026, 7, 17), "broken_limit_count": 3}
        ]

    @pytest.mark.asyncio
    async def test_collect_error_returns_empty(self) -> None:
        collector = EastmoneyBrokenPoolCollector(
            {"source": "eastmoney", "data_type": "broken-pool"}
        )
        with patch("akshare.stock_zt_pool_zbgc_em", side_effect=ValueError("x")):
            assert await collector.collect(
                trade_date=datetime.date(2026, 7, 17)
            ) == []


@pytest.mark.unit
class TestEastmoneyLimitDownPoolCollector:
    @pytest.mark.asyncio
    async def test_collect_counts_limit_down_pool(self) -> None:
        collector = EastmoneyLimitDownPoolCollector(
            {"source": "eastmoney", "data_type": "limit-down-pool"}
        )
        mock_df = pd.DataFrame({"代码": ["000001", "000002"]})
        with patch("akshare.stock_zt_pool_dtgc_em", return_value=mock_df):
            raw = await collector.collect(trade_date=datetime.date(2026, 7, 17))

        assert raw == [
            {"trade_date": datetime.date(2026, 7, 17), "limit_down_count": 2}
        ]

    @pytest.mark.asyncio
    async def test_collect_error_returns_empty(self) -> None:
        collector = EastmoneyLimitDownPoolCollector(
            {"source": "eastmoney", "data_type": "limit-down-pool"}
        )
        with patch("akshare.stock_zt_pool_dtgc_em", side_effect=ValueError("x")):
            assert await collector.collect(
                trade_date=datetime.date(2026, 7, 17)
            ) == []

    @pytest.mark.asyncio
    async def test_collect_skips_non_trading_day(self) -> None:
        collector = EastmoneyLimitDownPoolCollector(
            {"source": "eastmoney", "data_type": "limit-down-pool"}
        )
        with (
            patch(
                "collector.spiders.eastmoney_limit_down_pool.is_trading_day",
                return_value=False,
            ),
            patch(
                "akshare.stock_zt_pool_dtgc_em",
                side_effect=AssertionError("不应请求接口"),
            ),
        ):
            assert await collector.collect(
                trade_date=datetime.date(2026, 7, 19)
            ) == []
