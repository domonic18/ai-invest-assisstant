"""Unit tests for research API endpoints."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
class TestResearchEndpoints:
    def _report_mock(self, report_id: int = 1) -> MagicMock:
        report = MagicMock()
        report.id = report_id
        report.stock_code = "000001"
        report.title = "Test Report"
        report.summary = "summary"
        report.content = "content"
        report.source = "broker"
        report.source_url = "http://example.com"
        report.publish_date = datetime(2024, 1, 1, 0, 0, 0)
        report.sentiment = None
        report.keywords = None
        report.industry_tags = None
        report.extra = {}
        report.created_at = datetime(2024, 1, 1, 0, 0, 0)
        return report

    @patch("app.api.v1.research.research_service.list_reports")
    def test_list_research(self, mock_list, client) -> None:
        mock_list.return_value = ([self._report_mock()], 1)
        response = client.get("/api/v1/research/?stock_code=000001")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["stock_code"] == "000001"

    @patch("app.api.v1.research.research_service.get_report")
    def test_get_research(self, mock_get, client) -> None:
        mock_get.return_value = self._report_mock()
        response = client.get("/api/v1/research/1")
        assert response.status_code == 200
        assert response.json()["title"] == "Test Report"

    @patch("app.api.v1.research.research_service.get_report")
    def test_get_research_not_found(self, mock_get, client) -> None:
        mock_get.return_value = None
        response = client.get("/api/v1/research/999")
        assert response.status_code == 404

    @patch("app.api.v1.research.research_service.summarize_report")
    def test_summarize_research(self, mock_summarize, client) -> None:
        mock_summarize.return_value = {"summary": "great report"}
        response = client.post("/api/v1/research/1/summarize")
        assert response.status_code == 200
        assert response.json()["summary"] == "great report"
