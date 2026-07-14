"""Unit tests for collector task entry functions."""

from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from collector.base import CollectStatus
from collector.tasks import (
    collect_financial_report,
    collect_fund_holdings,
    collect_ipo_info,
)


@pytest.mark.unit
class TestCollectorTaskEntries:
    @pytest.mark.asyncio
    async def test_collect_financial_report_end_to_end(self) -> None:
        mock_df = pd.DataFrame(
            [
                {
                    "股票代码": "000001",
                    "股票简称": "平安银行",
                    "公告标题": "2023年年度报告",
                    "公告时间": "2024-03-15 00:00:00",
                    "公告类型": "年报",
                    "公告链接": "http://example.com/report/1",
                }
            ]
        )

        with (
            patch(
                "collector.tasks._resolve_task_channel",
                AsyncMock(return_value=("cninfo", {"base_url": None, "api_key": None})),
            ),
            patch(
                "akshare.stock_zh_a_disclosure_report_cninfo",
                return_value=mock_df,
            ),
            patch(
                "collector.spiders.cninfo_financial_report.CninfoFinancialReportCollector.store",
                AsyncMock(return_value=1),
            ),
        ):
            result = await collect_financial_report()

        assert result.status == CollectStatus.SUCCESS
        assert result.items_collected >= 1
        assert result.items_stored == 1

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
                "collector.tasks._resolve_task_channel",
                AsyncMock(return_value=("cninfo", {"base_url": None, "api_key": None})),
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
                "collector.tasks._resolve_task_channel",
                AsyncMock(return_value=("eastmoney", {"base_url": None, "api_key": None})),
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
