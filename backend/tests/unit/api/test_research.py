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
        report.industry_tags = ["自动化设备"]
        report.extra = {"broker": "开源证券", "rating": "买入", "pages": 29}
        report.created_at = datetime(2024, 1, 1, 0, 0, 0)
        report.broker = None
        report.rating = None
        report.pages = None
        report.industry = None
        report.has_summary = False
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

    @patch("app.api.v1.research.research_service.list_reports")
    def test_list_research_derived_fields(self, mock_list, client) -> None:
        mock_list.return_value = ([self._report_mock()], 1)
        response = client.get("/api/v1/research/")
        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["broker"] == "开源证券"
        assert item["rating"] == "买入"
        assert item["pages"] == 29
        assert item["industry"] == "自动化设备"
        assert item["has_summary"] is True

    @patch("app.api.v1.research.research_service.list_reports")
    def test_list_research_passes_broker_industry(self, mock_list, client) -> None:
        mock_list.return_value = ([], 0)
        response = client.get(
            "/api/v1/research/?broker=开源证券&industry=自动化设备"
        )
        assert response.status_code == 200
        kwargs = mock_list.await_args.kwargs
        assert kwargs["broker"] == "开源证券"
        assert kwargs["industry"] == "自动化设备"

    @patch("app.api.v1.research.research_service.list_filters")
    def test_list_filters(self, mock_filters, client) -> None:
        mock_filters.return_value = {
            "brokers": ["开源证券", "中信证券"],
            "industries": ["自动化设备", "煤炭开采"],
        }
        response = client.get("/api/v1/research/filters")
        assert response.status_code == 200
        assert response.json() == {
            "brokers": ["开源证券", "中信证券"],
            "industries": ["自动化设备", "煤炭开采"],
        }

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

    @patch("app.api.v1.research.research_service.get_pdf_url")
    def test_pdf_url(self, mock_pdf_url, client) -> None:
        mock_pdf_url.return_value = "http://minio/presigned"
        response = client.get("/api/v1/research/1/pdf-url")
        assert response.status_code == 200
        assert response.json() == {"url": "http://minio/presigned"}

    @patch("app.api.v1.research.research_service.get_pdf_url")
    def test_pdf_url_not_available(self, mock_pdf_url, client) -> None:
        mock_pdf_url.return_value = None
        response = client.get("/api/v1/research/1/pdf-url")
        assert response.status_code == 404

    @patch("app.api.v1.research.research_service.summarize_report")
    def test_summarize_research(self, mock_summarize, client) -> None:
        mock_summarize.return_value = {"summary": "great report", "cached": True}
        response = client.post("/api/v1/research/1/summarize")
        assert response.status_code == 200
        assert response.json()["summary"] == "great report"
