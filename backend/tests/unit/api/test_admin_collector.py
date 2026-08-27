"""Unit tests for admin collector trigger API."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_admin_user, get_db
from app.main import app


@pytest.fixture
def admin_client(client) -> tuple[TestClient, AsyncMock]:
    """Return a client with admin auth and a mock database session."""
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
class TestAdminCollectorEndpoints:
    @patch("app.api.v1.admin.collector.dispatch_collector_task")
    def test_run_collector_task_dispatches_to_queue(
        self,
        mock_dispatch: AsyncMock,
        admin_client: tuple[TestClient, AsyncMock],
    ) -> None:
        mock_log = MagicMock()
        mock_log.id = 42
        mock_log.celery_task_id = "celery-uuid"
        mock_dispatch.return_value = mock_log
        client, _ = admin_client

        response = client.post(
            "/api/v1/admin/collector/tasks/financial-report/run",
            json={"preferred_source": "cninfo", "symbols": ["000001"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["task_name"] == "financial-report"
        assert data["status"] == "dispatched"
        assert data["log_id"] == 42
        assert data["celery_task_id"] == "celery-uuid"
        mock_dispatch.assert_awaited_once()
        call_kwargs = mock_dispatch.await_args.kwargs
        assert call_kwargs["task_name"] == "financial-report"
        assert call_kwargs["params"]["preferred_source"] == "cninfo"

    @patch("app.api.v1.admin.collector.list_channels_for_task")
    @patch("app.api.v1.admin.collector.resolve_channel_for_task")
    def test_get_collector_task_channels(
        self,
        mock_resolve: AsyncMock,
        mock_list: AsyncMock,
        admin_client: tuple[TestClient, AsyncMock],
    ) -> None:
        mock_list.return_value = [
            {"source": "cninfo", "name": "巨潮资讯", "is_enabled": True}
        ]
        resolved = MagicMock()
        resolved.source = "cninfo"
        mock_resolve.return_value = resolved
        client, _ = admin_client

        response = client.get("/api/v1/admin/collector/tasks/financial-report/channels")

        assert response.status_code == 200
        data = response.json()
        assert data["task_name"] == "financial-report"
        assert data["resolved_source"] == "cninfo"
        assert len(data["channels"]) == 1
