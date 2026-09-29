"""后台题材映射端点契约测试。"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import ConflictError, NotFoundError
from app.dependencies import get_current_admin_user, get_db
from app.main import app


@pytest.fixture
def admin_client(client) -> tuple[TestClient, AsyncMock]:
    """返回已绕过管理员认证并注入 mock session 的客户端。"""
    mock_session = AsyncMock()
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.role = "admin"

    async def _override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_admin_user] = lambda: mock_user
    yield client, mock_session
    app.dependency_overrides.clear()


def _row_mock() -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        stock_code="600703",
        stock_name="三安光电",
        concept_code="881234",
        concept_name="Mini LED",
        source="manual",
        updated_at=datetime(2026, 9, 29, 8, 0, tzinfo=timezone.utc),
    )


@pytest.mark.unit
class TestAdminStockConceptEndpoints:
    @patch("app.api.v1.admin.stock_concepts.AdminStockConceptService")
    def test_list_returns_paginated(self, mock_service, admin_client) -> None:
        mock_service.return_value.list_concepts = AsyncMock(
            return_value=([_row_mock()], 1)
        )
        client, _ = admin_client
        response = client.get(
            "/api/v1/admin/stock-concepts/", params={"q": "600703", "concept": "led"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        item = body["items"][0]
        assert item["stockCode"] == "600703"
        assert item["stockName"] == "三安光电"
        assert item["conceptName"] == "Mini LED"

    @patch("app.api.v1.admin.stock_concepts.AdminStockConceptService")
    def test_create_marks_manual_source(self, mock_service, admin_client) -> None:
        mock_service.return_value.create_concept = AsyncMock(
            return_value={
                "id": 1,
                "stock_code": "600703",
                "stock_name": "三安光电",
                "concept_code": "881234",
                "concept_name": "Mini LED",
                "source": "manual",
                "updated_at": datetime(2026, 9, 29, 8, 0, tzinfo=timezone.utc),
            }
        )
        client, _ = admin_client
        response = client.post(
            "/api/v1/admin/stock-concepts/",
            json={"stockCode": "600703", "conceptCode": "881234", "conceptName": "Mini LED"},
        )
        assert response.status_code == 201
        assert response.json()["source"] == "manual"

    @patch("app.api.v1.admin.stock_concepts.AdminStockConceptService")
    def test_create_conflict_maps_409(self, mock_service, admin_client) -> None:
        mock_service.return_value.create_concept = AsyncMock(
            side_effect=ConflictError("该股票已存在相同概念代码的映射")
        )
        client, _ = admin_client
        response = client.post(
            "/api/v1/admin/stock-concepts/",
            json={"stockCode": "600703", "conceptCode": "881234", "conceptName": "Mini LED"},
        )
        assert response.status_code == 409

    @patch("app.api.v1.admin.stock_concepts.AdminStockConceptService")
    def test_update_maps_not_found_404(self, mock_service, admin_client) -> None:
        mock_service.return_value.update_concept = AsyncMock(
            side_effect=NotFoundError("Stock concept 999 not found")
        )
        client, _ = admin_client
        response = client.put(
            "/api/v1/admin/stock-concepts/999", json={"conceptName": "改名"}
        )
        assert response.status_code == 404

    @patch("app.api.v1.admin.stock_concepts.AdminStockConceptService")
    def test_delete_returns_204(self, mock_service, admin_client) -> None:
        mock_service.return_value.delete_concept = AsyncMock(return_value=None)
        client, _ = admin_client
        response = client.delete("/api/v1/admin/stock-concepts/1")
        assert response.status_code == 204

    def test_create_validates_required_fields(self, admin_client) -> None:
        client, _ = admin_client
        response = client.post(
            "/api/v1/admin/stock-concepts/",
            json={"stockCode": "600703"},
        )
        assert response.status_code == 422
