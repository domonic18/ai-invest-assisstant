"""基本面与基础资料 spider 契约测试。"""


import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from collector.spiders.cninfo_financial_report import CninfoFinancialReportCollector
from collector.spiders.cninfo_ipo import CninfoIpoCollector
from collector.spiders.eastmoney_financial_statement import (
    EastmoneyFinancialStatementCollector,
)
from collector.spiders.eastmoney_fund_holdings import EastMoneyFundHoldingsCollector


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
