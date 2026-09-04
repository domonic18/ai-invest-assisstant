"""财务健康度 API 端点契约测试。"""

from datetime import date
from unittest.mock import patch

import pytest

from app.schemas.financial import FinancialHealthResponse


@pytest.mark.unit
class TestFinancialEndpoints:
    @patch("app.api.v1.financial.financial_service.get_health")
    def test_get_financial_health(self, mock_get_health, client) -> None:
        mock_get_health.return_value = FinancialHealthResponse(
            stock_code="000001",
            report_date=date(2024, 3, 31),
            report_type="年报",
            metrics={
                "debt_ratio": 0.5,
                "current_ratio": 2.0,
            },
        )
        response = client.get("/api/v1/financial/000001")
        assert response.status_code == 200
        data = response.json()
        assert data["stock_code"] == "000001"
        assert data["metrics"]["debt_ratio"] == 0.5

    @patch("app.api.v1.financial.financial_service.get_health")
    def test_get_financial_health_with_report_date(self, mock_get_health, client) -> None:
        mock_get_health.return_value = FinancialHealthResponse(
            stock_code="000001",
            report_date=date(2023, 12, 31),
            report_type="年报",
            metrics={},
        )
        response = client.get("/api/v1/financial/000001?report_date=2023-12-31")
        assert response.status_code == 200
        assert response.json()["report_date"] == "2023-12-31"

    @patch("app.api.v1.financial.financial_service.get_health_history")
    def test_get_financial_health_history(self, mock_get_history, client) -> None:
        mock_get_history.return_value = [
            FinancialHealthResponse(
                stock_code="000001",
                report_date=date(2023, 12, 31),
                report_type="annual",
                metrics={"debt_ratio": 0.4},
            ),
            FinancialHealthResponse(
                stock_code="000001",
                report_date=date(2024, 3, 31),
                report_type="q1",
                metrics={"debt_ratio": 0.5},
            ),
        ]
        response = client.get("/api/v1/financial/000001/history?limit=8")
        assert response.status_code == 200
        data = response.json()
        assert data["stock_code"] == "000001"
        assert len(data["history"]) == 2
        assert data["history"][0]["report_date"] == "2023-12-31"
        assert data["history"][1]["report_date"] == "2024-03-31"
