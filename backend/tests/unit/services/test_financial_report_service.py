"""财务报告服务契约测试。"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import NotFoundError
from app.services.reports import financial_report_service
from app.services.reports.financial_report_summarizer import (
    FinancialReportSummaryResult,
    render_summary_markdown,
)


def _financial_report_mock(summary: str | None = None) -> MagicMock:
    report = MagicMock()
    report.id = 1
    report.file_type = "financial_report"
    report.summary = summary
    return report


@pytest.mark.unit
class TestFinancialReportService:
    @pytest.mark.asyncio
    async def test_get_report_rejects_non_financial_file_type(self) -> None:
        session = AsyncMock()
        report = MagicMock()
        report.file_type = "research_report"
        session.get.return_value = report

        result = await financial_report_service.get_report(session, 1)

        assert result is None

    @pytest.mark.asyncio
    async def test_summarize_report_returns_cached_summary(self) -> None:
        session = AsyncMock()
        session.get.return_value = _financial_report_mock(summary="existing summary")

        with patch(
            "app.services.reports.financial_report_summarizer.redis_lock"
        ) as mock_lock:
            result = await financial_report_service.summarize_report(session, 1)

        assert result == {"summary": "existing summary", "cached": True}
        mock_lock.assert_not_called()

    @pytest.mark.asyncio
    async def test_summarize_report_not_found(self) -> None:
        session = AsyncMock()
        session.get.return_value = None

        with pytest.raises(NotFoundError):
            await financial_report_service.summarize_report(session, 1)

    @pytest.mark.asyncio
    async def test_get_pdf_url_returns_none_without_file_path(self) -> None:
        session = AsyncMock()
        report = _financial_report_mock()
        report.file_path = ""
        session.get.return_value = report

        result = await financial_report_service.get_pdf_url(session, 1)

        assert result is None


@pytest.mark.unit
class TestRenderSummaryMarkdown:
    def test_renders_all_sections(self) -> None:
        output = FinancialReportSummaryResult(
            core_performance="- 营收同比增长 20%",
            revenue_profit="- 归母净利润 50 亿元",
            business_highlights="- 新业务放量",
            risk_warning="- 原材料价格波动",
            outlook="- 下半年产能释放",
        )
        markdown = render_summary_markdown(output)
        assert "### 核心业绩" in markdown
        assert "### 营收与利润" in markdown
        assert "### 经营亮点" in markdown
        assert "### 风险提示" in markdown
        assert "### 未来展望" in markdown

    def test_omits_empty_fields(self) -> None:
        output = FinancialReportSummaryResult(core_performance="- 营收增长")
        markdown = render_summary_markdown(output)
        assert "### 核心业绩" in markdown
        assert "风险提示" not in markdown
        assert "未来展望" not in markdown


@pytest.mark.unit
class TestListReportsSearch:
    @pytest.mark.asyncio
    async def test_q_resolves_stock_name_to_codes(self) -> None:
        session = AsyncMock()
        stock = MagicMock()
        stock.stock_code = "688322"

        with (
            patch(
                "app.services.reports.financial_report_service.FileMetadataRepository"
            ) as mock_repo_cls,
            patch(
                "app.services.reports.financial_report_service.StockRepository"
            ) as mock_stock_cls,
        ):
            mock_stock_cls.return_value.search = AsyncMock(
                return_value=([stock], 1)
            )
            mock_repo_cls.return_value.list_paginated = AsyncMock(
                return_value=([], 0)
            )

            await financial_report_service.list_reports(session, q="奥比中光")

        kwargs = mock_repo_cls.return_value.list_paginated.await_args.kwargs
        assert kwargs["q"] == "奥比中光"
        assert kwargs["q_stock_codes"] == ["688322"]

    @pytest.mark.asyncio
    async def test_no_q_skips_stock_lookup(self) -> None:
        session = AsyncMock()

        with (
            patch(
                "app.services.reports.financial_report_service.FileMetadataRepository"
            ) as mock_repo_cls,
            patch(
                "app.services.reports.financial_report_service.StockRepository"
            ) as mock_stock_cls,
        ):
            mock_repo_cls.return_value.list_paginated = AsyncMock(
                return_value=([], 0)
            )

            await financial_report_service.list_reports(session)

        mock_stock_cls.assert_not_called()
        kwargs = mock_repo_cls.return_value.list_paginated.await_args.kwargs
        assert kwargs["q_stock_codes"] is None


@pytest.mark.unit
class TestToReportResponse:
    def test_derives_title_and_has_summary(self) -> None:
        from datetime import datetime

        report = MagicMock()
        report.id = 1
        report.stock_code = "000001"
        report.original_name = "2025年年度报告"
        report.title = None
        report.stock_name = None
        report.report_type = "annual"
        report.report_date = None
        report.file_size = 1024
        report.summary = "摘要"
        report.created_at = datetime(2026, 3, 15)

        response = financial_report_service.to_report_response(
            report, stock_name="平安银行"
        )

        assert response.title == "2025年年度报告"
        assert response.stock_name == "平安银行"
        assert response.has_summary is True


@pytest.mark.unit
class TestTriggerCollect:
    @pytest.mark.asyncio
    async def test_dispatches_cninfo_with_symbols(self) -> None:
        session = AsyncMock()
        stock = MagicMock()
        stock.stock_code = "002156"
        search_result = MagicMock()
        search_result.scalars.return_value.all.return_value = [stock]
        session.execute.return_value = search_result
        session.scalar.return_value = 1

        log = MagicMock()
        log.id = 42
        log.status = "pending"

        with patch(
            "collector.runtime.dispatcher.dispatch_collector_task",
            new=AsyncMock(return_value=log),
        ) as mock_dispatch:
            result = await financial_report_service.trigger_collect(
                session,
                stock_code="002156",
                report_types=["annual"],
                start_date=date(2026, 1, 1),
                end_date=date(2026, 6, 30),
            )

        assert result is log
        kwargs = mock_dispatch.await_args.kwargs
        assert kwargs["task_name"] == "financial-report"
        assert kwargs["params"]["symbols"] == ["002156"]
        assert kwargs["params"]["preferred_source"] == "cninfo"
        assert kwargs["params"]["report_types"] == ["annual"]
        assert kwargs["params"]["start_date"] == "2026-01-01"
        assert kwargs["params"]["end_date"] == "2026-06-30"

    @pytest.mark.asyncio
    async def test_unknown_stock_raises(self) -> None:
        session = AsyncMock()
        search_result = MagicMock()
        search_result.scalars.return_value.all.return_value = []
        session.execute.return_value = search_result
        session.scalar.return_value = 0

        with pytest.raises(NotFoundError):
            await financial_report_service.trigger_collect(
                session, stock_code="999999"
            )

    @pytest.mark.asyncio
    async def test_get_collect_log_rejects_other_task(self) -> None:
        session = AsyncMock()
        log = MagicMock()
        log.task_name = "research-report"
        session.get.return_value = log

        result = await financial_report_service.get_collect_log(session, 42)

        assert result is None
