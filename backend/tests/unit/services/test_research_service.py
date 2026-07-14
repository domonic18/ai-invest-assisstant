"""Unit tests for research service."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import research_service


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
    async def test_summarize_report_returns_existing_summary(self) -> None:
        session = AsyncMock()
        report = MagicMock()
        report.summary = "existing summary"
        report.content = "content"
        session.get.return_value = report

        result = await research_service.summarize_report(session, 1)

        assert result == {"summary": "existing summary"}

    @pytest.mark.asyncio
    async def test_summarize_report_falls_back_to_content(self) -> None:
        session = AsyncMock()
        report = MagicMock()
        report.summary = None
        report.content = "a" * 600
        session.get.return_value = report

        result = await research_service.summarize_report(session, 1)

        assert result["summary"].endswith("...")
        assert len(result["summary"]) == 503

    @pytest.mark.asyncio
    async def test_summarize_report_not_found(self) -> None:
        session = AsyncMock()
        session.get.return_value = None

        with pytest.raises(ValueError):
            await research_service.summarize_report(session, 1)
