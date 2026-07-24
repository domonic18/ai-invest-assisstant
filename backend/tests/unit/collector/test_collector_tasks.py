"""Unit tests for collector task entry functions."""

from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from collector.core.base import CollectStatus
from collector.runtime.registry import TASK_MAP

collect_financial_report = TASK_MAP["financial-report"]
collect_fund_holdings = TASK_MAP["fund-holdings"]
collect_ipo_info = TASK_MAP["ipo-info"]
collect_stock_list = TASK_MAP["stock-list"]


@pytest.mark.unit
class TestCollectorTaskEntries:
    @pytest.mark.asyncio
    async def test_collect_financial_report_end_to_end(self) -> None:
        balance_df = pd.DataFrame(
            [
                {
                    "REPORT_DATE": "2024-03-31 00:00:00",
                    "REPORT_TYPE": "一季报",
                    "TOTAL_ASSETS": 1000000.0,
                    "TOTAL_LIABILITIES": 400000.0,
                    "TOTAL_EQUITY": 600000.0,
                }
            ]
        )
        income_df = pd.DataFrame(
            [
                {
                    "REPORT_DATE": "2024-03-31 00:00:00",
                    "REPORT_TYPE": "一季报",
                    "TOTAL_OPERATE_INCOME": 200000.0,
                    "TOTAL_OPERATE_COST": 120000.0,
                    "NETPROFIT": 50000.0,
                    "BASIC_EPS": 0.5,
                }
            ]
        )
        cash_df = pd.DataFrame(
            [
                {
                    "REPORT_DATE": "2024-03-31 00:00:00",
                    "REPORT_TYPE": "一季报",
                    "NETCASH_OPERATE": 30000.0,
                    "NETCASH_INVEST": -10000.0,
                    "NETCASH_FINANCE": -5000.0,
                    "CCE_ADD": 15000.0,
                }
            ]
        )

        with (
            patch(
                "collector.runtime.registry._resolve_task_channels",
                AsyncMock(return_value=[("eastmoney", {"base_url": None, "api_key": None})]),
            ),
            patch(
                "akshare.stock_balance_sheet_by_report_em",
                return_value=balance_df,
            ),
            patch(
                "akshare.stock_profit_sheet_by_report_em",
                return_value=income_df,
            ),
            patch(
                "akshare.stock_cash_flow_sheet_by_report_em",
                return_value=cash_df,
            ),
            patch(
                "collector.spiders.eastmoney_financial_statement.EastmoneyFinancialStatementCollector.store",
                AsyncMock(return_value=3),
            ),
        ):
            result = await collect_financial_report()

        assert result.status == CollectStatus.SUCCESS
        assert result.items_collected >= 1
        assert result.items_stored == 3

    @pytest.mark.asyncio
    async def test_collect_ipo_info_end_to_end(self) -> None:
        mock_df = pd.DataFrame(
            [
                {
                    "证劵代码": "001387",
                    "证券简称": "Test IPO",
                    "上市日期": "2024-01-15",
                    "申购日期": "2024-01-05",
                    "发行价": 10.0,
                    "总发行数量": 5000000,
                    "发行市盈率": 22.5,
                    "上网发行中签率": 0.03,
                    "摇号结果公告日": "2024-01-08",
                    "中签公告日": "2024-01-09",
                    "中签缴款日": "2024-01-10",
                    "网上申购上限": 10000,
                    "上网发行数量": 4500000,
                }
            ]
        )

        with (
            patch(
                "collector.runtime.registry._resolve_task_channels",
                AsyncMock(return_value=[("cninfo", {"base_url": None, "api_key": None})]),
            ),
            patch(
                "akshare.stock_new_ipo_cninfo",
                return_value=mock_df,
            ),
            patch(
                "collector.spiders.cninfo_ipo.CninfoIpoCollector.store",
                AsyncMock(return_value=1),
            ),
        ):
            result = await collect_ipo_info()

        assert result.status == CollectStatus.SUCCESS
        assert result.items_collected == 1
        assert result.items_stored == 1

    @pytest.mark.asyncio
    async def test_collect_fund_holdings_end_to_end(self) -> None:
        mock_df = pd.DataFrame(
            [
                {
                    "股票代码": "000001",
                    "股票简称": "平安银行",
                    "持有基金家数": 100,
                    "持股总数": 5000000,
                    "持股市值": 50000000.0,
                    "持股变化": "增持",
                    "持股变动数值": 100000,
                    "持股变动比例": 0.02,
                }
            ]
        )

        with (
            patch(
                "collector.runtime.registry._resolve_task_channels",
                AsyncMock(return_value=[("eastmoney", {"base_url": None, "api_key": None})]),
            ),
            patch(
                "akshare.stock_report_fund_hold",
                return_value=mock_df,
            ),
            patch(
                "collector.spiders.eastmoney_fund_holdings.EastMoneyFundHoldingsCollector.store",
                AsyncMock(return_value=1),
            ),
        ):
            result = await collect_fund_holdings(report_date="20250331")

        assert result.status == CollectStatus.SUCCESS
        assert result.items_collected == 1
        assert result.items_stored == 1

    @pytest.mark.asyncio
    async def test_collect_stock_list_end_to_end(self) -> None:
        mock_df = pd.DataFrame(
            [
                {"code": "000001", "name": "平安银行"},
                {"code": "600000", "name": "浦发银行"},
            ]
        )
        details = {
            "000001": {"total_shares": 19405918198},
            "600000": {"full_name": "上海浦东发展银行股份有限公司"},
        }
        industries = {
            "000001": {
                "industry_level_1": "银行",
                "industry_level_2": "全国性银行",
                "industry_level_3": "股份制银行",
            }
        }

        with (
            patch(
                "collector.runtime.registry._resolve_task_channels",
                AsyncMock(return_value=[("sina", {"base_url": None, "api_key": None})]),
            ),
            patch(
                "akshare.stock_info_a_code_name",
                return_value=mock_df,
            ),
            patch(
                "collector.spiders.sina_stock_list._fetch_exchange_details",
                return_value=details,
            ),
            patch(
                "collector.spiders.sina_stock_list._fetch_sw_industry_map",
                return_value=industries,
            ),
            patch(
                "collector.spiders.sina_stock_list.SinaStockListCollector.store",
                AsyncMock(return_value=2),
            ),
        ):
            result = await collect_stock_list()

        assert result.status == CollectStatus.SUCCESS
        assert result.items_collected == 2
        assert result.items_stored == 2

    @pytest.mark.asyncio
    async def test_collect_financial_report_via_cninfo(self) -> None:
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

        with (
            patch(
                "collector.runtime.registry._resolve_task_channels",
                AsyncMock(return_value=[("cninfo", {"base_url": None, "api_key": None})]),
            ),
            patch(
                "collector.stores.financial_report_store.FinancialReportStore.save_many",
                AsyncMock(return_value=(1, [])),
            ),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await collect_financial_report(
                symbols=["000001"],
                start_date="2024-01-01",
                end_date="2024-12-31",
                report_types=["年报"],
            )

        assert result.status == CollectStatus.SUCCESS
        assert result.items_collected == 1
        assert result.items_stored == 1


def _result(source: str, status: CollectStatus, errors: list[str] | None = None):
    from datetime import datetime, timezone

    from collector.core.base import CollectResult

    now = datetime.now(timezone.utc)
    return CollectResult(
        source=source,
        data_type="capital_fund_flow_sector",
        status=status,
        items_collected=0,
        items_stored=0,
        errors=errors or [],
        started_at=now,
        finished_at=now,
    )


@pytest.mark.unit
class TestRunCollectorFallback:
    @pytest.fixture
    def collectors(self):
        from collector.core.base import BaseCollector

        class FakeCollector(BaseCollector):
            result = None

            def __init__(self, config):
                super().__init__(config)

            async def collect(self, **kwargs):
                return []

            async def transform(self, raw):
                return raw

            async def validate(self, item):
                return True

            async def run(self, **kwargs):
                return type(self).result

        return FakeCollector

    @pytest.mark.asyncio
    async def test_fallback_to_second_source_on_failure(self, collectors) -> None:
        from collector.runtime import registry as tasks

        results = [
            _result("eastmoney", CollectStatus.FAILED, ["连接被拒"]),
            _result("ths", CollectStatus.SUCCESS),
        ]
        call_count = {"n": 0}

        class SeqCollector(collectors):
            async def run(self, **kwargs):
                outcome = results[call_count["n"]]
                call_count["n"] += 1
                return outcome

        with patch(
            "collector.runtime.registry._resolve_task_channels",
            AsyncMock(
                return_value=[
                    ("eastmoney", {"base_url": None, "api_key": None}),
                    ("ths", {"base_url": None, "api_key": None}),
                ]
            ),
        ):
            result = await tasks._run_collector_for_task(
                "sector-fund-flow",
                "capital_fund_flow_sector",
                {"eastmoney": SeqCollector, "ths": SeqCollector},
                None,
            )

        assert result.status == CollectStatus.SUCCESS
        assert result.source == "ths"
        assert any("[eastmoney]" in error for error in result.errors)

    @pytest.mark.asyncio
    async def test_all_failed_returns_aggregated_errors(self, collectors) -> None:
        from collector.runtime import registry as tasks

        class FailCollector(collectors):
            async def run(self, **kwargs):
                return _result(self.source, CollectStatus.FAILED, [f"{self.source} 失败"])

        with patch(
            "collector.runtime.registry._resolve_task_channels",
            AsyncMock(
                return_value=[
                    ("eastmoney", {"base_url": None, "api_key": None}),
                    ("ths", {"base_url": None, "api_key": None}),
                ]
            ),
        ):
            result = await tasks._run_collector_for_task(
                "sector-fund-flow",
                "capital_fund_flow_sector",
                {"eastmoney": FailCollector, "ths": FailCollector},
                None,
            )

        assert result.status == CollectStatus.FAILED
        assert any("[eastmoney]" in error for error in result.errors)
        assert any("[ths]" in error for error in result.errors)

    @pytest.mark.asyncio
    async def test_source_without_collector_is_skipped(self, collectors) -> None:
        from collector.runtime import registry as tasks

        class OkCollector(collectors):
            async def run(self, **kwargs):
                return _result(self.source, CollectStatus.SUCCESS)

        with patch(
            "collector.runtime.registry._resolve_task_channels",
            AsyncMock(
                return_value=[
                    ("unknown-src", {"base_url": None, "api_key": None}),
                    ("ths", {"base_url": None, "api_key": None}),
                ]
            ),
        ):
            result = await tasks._run_collector_for_task(
                "sector-fund-flow",
                "capital_fund_flow_sector",
                {"ths": OkCollector},
                None,
            )

        assert result.status == CollectStatus.SUCCESS
        assert result.source == "ths"
        assert any("unknown-src" in error for error in result.errors)

    @pytest.mark.asyncio
    async def test_no_candidates_returns_skipped(self) -> None:
        from collector.runtime import registry as tasks

        with patch(
            "collector.runtime.registry._resolve_task_channels",
            AsyncMock(return_value=[]),
        ):
            result = await tasks._run_collector_for_task(
                "sector-fund-flow", "capital_fund_flow_sector", {}, None
            )

        assert result.status == CollectStatus.SKIPPED
