"""Unit tests for research service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import research_service
from app.services.research_service import (
    ResearchReportSummaryResult,
    _derived_fields,
    _render_summary_markdown,
)


def _result_mock(items=None, scalar=None):
    result = MagicMock()
    result.scalars.return_value.all.return_value = items or []
    result.scalar_one_or_none.return_value = scalar
    return result


@pytest.mark.unit
class TestResearchService:
    @pytest.mark.asyncio
    async def test_list_reports_returns_items_and_total(self) -> None:
        session = AsyncMock()
        mock_report = MagicMock()
        session.execute.return_value = _result_mock([mock_report])
        session.scalar.return_value = 5

        items, total = await research_service.list_reports(session)

        assert items == [mock_report]
        assert total == 5
        session.execute.assert_called()

    @pytest.mark.asyncio
    async def test_get_report_found(self) -> None:
        session = AsyncMock()
        mock_report = MagicMock()
        session.get.return_value = mock_report

        result = await research_service.get_report(session, 1)

        assert result == mock_report
        session.get.assert_awaited_once_with(research_service.NewsAnnouncement, 1)

    @pytest.mark.asyncio
    async def test_summarize_report_returns_cached_summary(self) -> None:
        session = AsyncMock()
        report = MagicMock()
        report.summary = "existing summary"
        session.get.return_value = report

        with patch(
            "app.services.research_service.redis_lock"
        ) as mock_lock:
            result = await research_service.summarize_report(session, 1)

        assert result == {"summary": "existing summary", "cached": True}
        mock_lock.assert_not_called()

    @pytest.mark.asyncio
    async def test_summarize_report_not_found(self) -> None:
        session = AsyncMock()
        session.get.return_value = None

        with pytest.raises(ValueError):
            await research_service.summarize_report(session, 1)

    @pytest.mark.asyncio
    async def test_get_pdf_url_returns_none_without_file_path(self) -> None:
        session = AsyncMock()
        report = MagicMock()
        report.extra = {}
        session.get.return_value = report

        result = await research_service.get_pdf_url(session, 1)

        assert result is None


@pytest.mark.unit
class TestRenderSummaryMarkdown:
    def test_renders_all_sections(self) -> None:
        output = ResearchReportSummaryResult(
            rating="买入（维持）",
            target_price="15.2-16.8 元",
            core_logic="- 逻辑一\n- 逻辑二",
            earnings_forecast="- 2026 年 EPS 2.45 元",
            risk_warning="- 原材料价格波动",
        )
        markdown = _render_summary_markdown(output)
        assert "**投资评级**：买入（维持）" in markdown
        assert "**目标价**：15.2-16.8 元" in markdown
        assert "### 核心逻辑" in markdown
        assert "### 盈利预测" in markdown
        assert "### 风险提示" in markdown

    def test_omits_empty_fields(self) -> None:
        output = ResearchReportSummaryResult(core_logic="- 逻辑一")
        markdown = _render_summary_markdown(output)
        assert "投资评级" not in markdown
        assert "目标价" not in markdown
        assert "### 核心逻辑" in markdown
        assert "风险提示" not in markdown


@pytest.mark.unit
class TestDerivedFields:
    def test_derives_from_extra_and_tags(self) -> None:
        report = MagicMock()
        report.extra = {"broker": "开源证券", "rating": "增持", "pages": 29}
        report.industry_tags = ["自动化设备"]
        report.summary = "摘要"

        fields = _derived_fields(report)

        assert fields == {
            "broker": "开源证券",
            "rating": "增持",
            "pages": 29,
            "industry": "自动化设备",
            "has_summary": True,
        }
