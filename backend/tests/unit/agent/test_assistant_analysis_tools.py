"""agent 个股分析/财报工具单测（mock service，不触网不连库）。"""


from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.tools import (
    download_financial_reports,
    persist_stock_daily_analysis,
    query_financial_reports,
    summarize_financial_report,
)


@pytest.mark.unit
class TestStockDailyAnalysisTool:
    @pytest.mark.asyncio
    async def test_persists_sections_and_emits_event(self) -> None:
        cfg = MagicMock()
        cfg.provider = "anthropic"
        cfg.model_name = "kimi"
        analysis = MagicMock()
        analysis.stock_code = "600519"
        analysis.stock_name = "贵州茅台"
        analysis.trade_date = date(2026, 9, 4)
        analysis.sections = [MagicMock(title="操作策略")]
        sections = {
            "intraday_review": "盘面解读",
            "key_events": "关键事件",
            "strategy": "操作策略",
            "risk_lines": "风险与止损",
        }
        with (
            patch(
                "app.services.admin.llm_config_service.resolve_default_llm",
                AsyncMock(return_value=cfg),
            ),
            patch(
                "app.services.review.stock_daily_analysis_service.persist_stock_analysis",
                AsyncMock(return_value=analysis),
            ) as persist_mock,
        ):
            result = await persist_stock_daily_analysis.ainvoke(
                {
                    "stock_code": "600519",
                    "trade_date": "2026-09-04",
                    "sections": sections,
                }
            )

        _, kwargs = persist_mock.await_args
        assert kwargs["trade_date"] == date(2026, 9, 4)
        assert kwargs["contents"] == sections
        assert kwargs["model"] == "anthropic/kimi"
        assert result["stock_code"] == "600519"
        assert result["stock_name"] == "贵州茅台"
        assert result["section_titles"] == ["操作策略"]
        assert result["__event__"] == {
            "type": "stock_daily_analysis.complete",
            "stock_code": "600519",
            "trade_date": "2026-09-04",
        }

    @pytest.mark.asyncio
    async def test_rejects_bad_trade_date(self) -> None:
        result = await persist_stock_daily_analysis.ainvoke(
            {"stock_code": "600519", "trade_date": "2026/09/04", "sections": {}}
        )
        assert "error" in result


@pytest.mark.unit
class TestFinancialReportTools:
    @pytest.mark.asyncio
    async def test_query_financial_reports(self) -> None:
        item = MagicMock()
        item.id = 7
        item.stock_code = "000001"
        item.report_type = "annual"
        item.report_date = date(2025, 12, 31)
        item.original_name = "平安银行2025年报.pdf"
        item.file_path = "financial_reports/000001_2025_annual.pdf"
        item.summary = "summary text"
        item.created_at = date(2026, 4, 1)

        mock_service = MagicMock()
        mock_service.list_reports = AsyncMock(return_value=([item], 1))
        with patch(
            "app.services.reports.financial_report_service.FinancialReportService",
            return_value=mock_service,
        ):
            result = await query_financial_reports.ainvoke(
                {"stock_code": "000001", "report_type": "annual"}
            )
        assert result["total"] == 1
        assert result["reports"][0]["id"] == 7
        assert result["reports"][0]["has_pdf"] is True
        assert result["reports"][0]["has_summary"] is True

    @pytest.mark.asyncio
    async def test_download_financial_reports(self) -> None:
        log = MagicMock()
        log.id = 42
        log.status = "pending"
        mock_service = MagicMock()
        mock_service.trigger_collect = AsyncMock(return_value=log)
        with patch(
            "app.services.reports.financial_report_service.FinancialReportService",
            return_value=mock_service,
        ):
            result = await download_financial_reports.ainvoke(
                {"stock_code": "000001", "report_types": ["annual", "q3"]}
            )
        assert result["log_id"] == 42
        assert result["status"] == "pending"

    @pytest.mark.asyncio
    async def test_summarize_financial_report(self) -> None:
        mock_service = MagicMock()
        mock_service.summarize_report = AsyncMock(
            return_value={"summary": "营收增长 12%", "cached": False}
        )
        with patch(
            "app.services.reports.financial_report_service.FinancialReportService",
            return_value=mock_service,
        ):
            result = await summarize_financial_report.ainvoke({"report_id": 7})
        assert result["summary"] == "营收增长 12%"

    @pytest.mark.asyncio
    async def test_query_financial_reports_rejects_bad_date(self) -> None:
        result = await query_financial_reports.ainvoke(
            {"stock_code": "000001", "start_date": "2024/01/01"}
        )
        assert "error" in result
