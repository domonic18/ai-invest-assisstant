"""跟踪指数配置端点测试：CRUD 契约 + 非管理员 403。"""

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_admin_user, get_current_user, get_db
from app.main import app


def _config_mock() -> MagicMock:
    config = MagicMock()
    config.id = 1
    config.index_code = "GC00Y"
    config.index_name = "COMEX 黄金"
    config.market_category = "全球"
    config.data_source = "eastmoney"
    config.sort_order = 5
    config.is_enabled = True
    config.latest_close = None
    config.latest_change_pct = None
    config.latest_trade_date = None
    config.created_at = datetime(2026, 9, 1)
    config.updated_at = datetime(2026, 9, 1)
    # service._to_response 走构造函数，这里直接返回 schema 实例更稳
    from app.schemas.tracked_index import TrackedIndexResponse

    return TrackedIndexResponse(
        id=1,
        index_code="GC00Y",
        index_name="COMEX 黄金",
        market_category="全球",
        data_source="eastmoney",
        sort_order=5,
        is_enabled=True,
        latest_close=4363.6,
        latest_change_pct=-1.21,
        latest_trade_date=date(2026, 9, 1),
        created_at=datetime(2026, 9, 1),
        updated_at=datetime(2026, 9, 1),
    )


@pytest.fixture
def admin_client(client) -> tuple[TestClient, AsyncMock]:
    """绕过管理员认证并注入 mock session。"""
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


@pytest.mark.unit
class TestTrackedIndexEndpoints:
    @patch("app.api.v1.admin.tracked_index.TrackedIndexService")
    def test_list(self, mock_service, admin_client) -> None:
        mock_service.return_value.list_indexes = AsyncMock(
            return_value=[_config_mock()]
        )
        client, _ = admin_client
        response = client.get("/api/v1/admin/tracked-indexes")
        assert response.status_code == 200
        body = response.json()
        assert body[0]["index_code"] == "GC00Y"
        assert body[0]["latest_close"] == 4363.6

    @patch("app.api.v1.admin.tracked_index.TrackedIndexService")
    def test_create(self, mock_service, admin_client) -> None:
        mock_service.return_value.create_index = AsyncMock(
            return_value=_config_mock()
        )
        client, _ = admin_client
        response = client.post(
            "/api/v1/admin/tracked-indexes",
            json={
                "index_code": "GC00Y",
                "index_name": "COMEX 黄金",
                "market_category": "全球",
                "data_source": "eastmoney",
                "sort_order": 5,
                "is_enabled": True,
            },
        )
        assert response.status_code == 201

    @patch("app.api.v1.admin.tracked_index.TrackedIndexService")
    def test_create_invalid_enable_returns_400(self, mock_service, admin_client) -> None:
        mock_service.return_value.create_index = AsyncMock(
            side_effect=ValueError("无数据源的指标不允许启用")
        )
        client, _ = admin_client
        response = client.post(
            "/api/v1/admin/tracked-indexes",
            json={
                "index_code": "BTC",
                "index_name": "比特币",
                "market_category": "全球",
                "data_source": "eastmoney",
            },
        )
        assert response.status_code == 400
        assert "无数据源" in response.json()["detail"]

    @patch("app.api.v1.admin.tracked_index.TrackedIndexService")
    def test_toggle(self, mock_service, admin_client) -> None:
        row = MagicMock()
        row.id = 1
        row.is_enabled = False
        mock_service.return_value.toggle_index = AsyncMock(return_value=row)
        client, _ = admin_client
        response = client.patch("/api/v1/admin/tracked-indexes/1/toggle")
        assert response.status_code == 200
        assert response.json() == {"id": 1, "is_enabled": False}

    @patch("app.api.v1.admin.tracked_index.TrackedIndexService")
    def test_toggle_missing_returns_404(self, mock_service, admin_client) -> None:
        mock_service.return_value.toggle_index = AsyncMock(return_value=None)
        client, _ = admin_client
        response = client.patch("/api/v1/admin/tracked-indexes/99/toggle")
        assert response.status_code == 404

    @patch("app.api.v1.admin.tracked_index.TrackedIndexService")
    def test_update(self, mock_service, admin_client) -> None:
        mock_service.return_value.update_index = AsyncMock(
            return_value=_config_mock()
        )
        client, _ = admin_client
        response = client.put(
            "/api/v1/admin/tracked-indexes/1", json={"sort_order": 2}
        )
        assert response.status_code == 200

    @patch("app.api.v1.admin.tracked_index.TrackedIndexService")
    def test_delete(self, mock_service, admin_client) -> None:
        mock_service.return_value.delete_index = AsyncMock(return_value=None)
        client, _ = admin_client
        response = client.delete("/api/v1/admin/tracked-indexes/1")
        assert response.status_code == 204

    def test_requires_admin(self, client) -> None:
        """普通登录用户访问管理端点返回 403。"""
        normal_user = MagicMock()
        normal_user.id = 2
        normal_user.role = "user"
        app.dependency_overrides[get_current_user] = lambda: normal_user
        try:
            response = client.get("/api/v1/admin/tracked-indexes")
            assert response.status_code == 403
        finally:
            app.dependency_overrides.pop(get_current_user, None)
