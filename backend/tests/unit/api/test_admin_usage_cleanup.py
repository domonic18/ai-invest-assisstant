"""admin token 用量手动清理端点契约测试（camelCase wire + 鉴权参数透传）。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_admin_user, get_db
from app.main import app


@pytest.fixture
def admin_client(client) -> tuple[TestClient, MagicMock]:
    """绕过管理员认证并注入 mock session。"""
    mock_session = MagicMock()
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.role = "admin"

    async def _override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_admin_user] = lambda: mock_user
    yield client, mock_user
    app.dependency_overrides.clear()


@pytest.mark.unit
class TestUsageCleanupEndpoint:
    def test_cleanup_returns_camel_count_and_actor(self, admin_client) -> None:
        tc, mock_user = admin_client
        with patch(
            "app.api.v1.admin.account.usage_cleanup",
            new=AsyncMock(return_value=5),
        ) as mock_cleanup:
            resp = tc.post("/api/v1/admin/usage/cleanup")

        assert resp.status_code == 200
        assert resp.json() == {"removedCount": 5}
        kwargs = mock_cleanup.await_args.kwargs
        assert kwargs["actor_id"] == mock_user.id
        assert kwargs["ip"]

    def test_cleanup_requires_admin_auth(self) -> None:
        # 未注入认证 override 时走真实鉴权依赖，未带 token 应 401/403
        resp = TestClient(app).post("/api/v1/admin/usage/cleanup")
        assert resp.status_code in (401, 403)
