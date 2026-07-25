"""Unit tests for financial report API endpoints."""

from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
class TestFinancialReportEndpoints:
    def _report_mock(self, report_id: int = 1) -> MagicMock:
        report = MagicMock()
        report.id = report_id
        report.stock_code = "000001"
        report.original_name = "2025年年度报告"
        report.title = None
        report.stock_name = None
        report.file_type = "financial_report"
        report.report_type = "annual"
        report.report_date = date(2026, 3, 15)
        report.file_size = 2_400_000
        report.summary = "summary"
        report.created_at = datetime(2026, 3, 15, 0, 0, 0)
        return report

    @patch("app.api.v1.financial_report.financial_report_service.get_stock_names")
    @patch("app.api.v1.financial_report.financial_report_service.list_reports")
    def test_list_financial_reports(
        self, mock_list, mock_names, client
    ) -> None:
        mock_list.return_value = ([self._report_mock()], 1)
        mock_names.return_value = {"000001": "平安银行"}
        response = client.get("/api/v1/financial-reports/?report_type=annual")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        item = data["items"][0]
        assert item["stock_code"] == "000001"
        assert item["stock_name"] == "平安银行"
        assert item["title"] == "2025年年度报告"
        assert item["report_type"] == "annual"
        assert item["has_summary"] is True
        kwargs = mock_list.await_args.kwargs
        assert kwargs["report_type"] == "annual"

    @patch("app.api.v1.financial_report.financial_report_service.get_stock_names")
    @patch("app.api.v1.financial_report.financial_report_service.list_reports")
    def test_list_financial_reports_passes_filters(
        self, mock_list, mock_names, client
    ) -> None:
        mock_list.return_value = ([], 0)
        mock_names.return_value = {}
        response = client.get(
            "/api/v1/financial-reports/?q=年报&start_date=2026-01-01&end_date=2026-06-30"
        )
        assert response.status_code == 200
        kwargs = mock_list.await_args.kwargs
        assert kwargs["q"] == "年报"
        assert kwargs["start_date"].isoformat() == "2026-01-01"
        assert kwargs["end_date"].isoformat() == "2026-06-30"

    @patch("app.api.v1.financial_report.financial_report_service.get_stock_names")
    @patch("app.api.v1.financial_report.financial_report_service.get_report")
    def test_get_financial_report(self, mock_get, mock_names, client) -> None:
        mock_get.return_value = self._report_mock()
        mock_names.return_value = {"000001": "平安银行"}
        response = client.get("/api/v1/financial-reports/1")
        assert response.status_code == 200
        body = response.json()
        assert body["title"] == "2025年年度报告"
        assert body["stock_name"] == "平安银行"

    @patch("app.api.v1.financial_report.financial_report_service.get_report")
    def test_get_financial_report_not_found(self, mock_get, client) -> None:
        mock_get.return_value = None
        response = client.get("/api/v1/financial-reports/999")
        assert response.status_code == 404

    @patch("app.api.v1.financial_report.financial_report_service.get_pdf_url")
    def test_pdf_url(self, mock_pdf_url, client) -> None:
        mock_pdf_url.return_value = "http://minio/presigned"
        response = client.get("/api/v1/financial-reports/1/pdf-url")
        assert response.status_code == 200
        assert response.json() == {"url": "http://minio/presigned"}

    @patch("app.api.v1.financial_report.financial_report_service.get_pdf_url")
    def test_pdf_url_not_available(self, mock_pdf_url, client) -> None:
        mock_pdf_url.return_value = None
        response = client.get("/api/v1/financial-reports/1/pdf-url")
        assert response.status_code == 404

    @patch("app.api.v1.financial_report.financial_report_service.summarize_report")
    def test_summarize_financial_report(self, mock_summarize, client) -> None:
        mock_summarize.return_value = {"summary": "great report", "cached": True}
        response = client.post("/api/v1/financial-reports/1/summarize")
        assert response.status_code == 200
        assert response.json()["summary"] == "great report"

    @patch("app.api.v1.financial_report.financial_report_service.trigger_collect")
    def test_collect_financial_report(self, mock_trigger, client) -> None:
        log = MagicMock()
        log.id = 42
        log.status = "pending"
        mock_trigger.return_value = log
        response = client.post(
            "/api/v1/financial-reports/collect",
            json={"stock_code": "002156", "report_types": ["annual"]},
        )
        assert response.status_code == 200
        assert response.json() == {"log_id": 42, "status": "pending"}
        kwargs = mock_trigger.await_args.kwargs
        assert kwargs["stock_code"] == "002156"
        assert kwargs["report_types"] == ["annual"]

    @patch("app.api.v1.financial_report.financial_report_service.trigger_collect")
    def test_collect_financial_report_unknown_stock(
        self, mock_trigger, client
    ) -> None:
        mock_trigger.side_effect = ValueError("股票 999999 不存在")
        response = client.post(
            "/api/v1/financial-reports/collect",
            json={"stock_code": "999999"},
        )
        assert response.status_code == 404

    @patch("app.api.v1.financial_report.financial_report_service.get_collect_log")
    def test_collect_log_status(self, mock_get_log, client) -> None:
        log = MagicMock()
        log.id = 42
        log.status = "success"
        log.records_count = 3
        log.error_msg = None
        log.finished_at = datetime(2026, 7, 25, 8, 0, 0)
        mock_get_log.return_value = log
        response = client.get("/api/v1/financial-reports/collect-logs/42")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
        assert body["records_count"] == 3

    @patch("app.api.v1.financial_report.financial_report_service.get_collect_log")
    def test_collect_log_not_found(self, mock_get_log, client) -> None:
        mock_get_log.return_value = None
        response = client.get("/api/v1/financial-reports/collect-logs/999")
        assert response.status_code == 404
