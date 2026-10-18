"""用户组后台 API 端点契约测试 + 路由级门控 API 验证。"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import ConflictError
from app.dependencies import get_current_admin_user, get_current_user
from app.main import app

_NOW = datetime(2026, 10, 18, tzinfo=timezone.utc)


def _group_row(group_id: int = 1, **overrides) -> SimpleNamespace:
    payload = {
        "id": group_id,
        "name": "外部访客",
        "description": None,
        "permissions": ["kb"],
        "is_active": True,
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


@pytest.fixture
def admin_client(client):
    app.dependency_overrides[get_current_admin_user] = lambda: SimpleNamespace(
        id=1, username="admin", role="admin", is_active=True
    )
    yield client
    app.dependency_overrides.pop(get_current_admin_user, None)


@pytest.mark.unit
class TestUserGroupApi:
    def test_list_features_returns_catalog(self, admin_client) -> None:
        response = admin_client.get("/api/v1/admin/user-groups/features")
        assert response.status_code == 200
        items = response.json()
        assert len(items) == 12
        assert {"key": "kb", "label": "知识库查询"} in items

    def test_list_groups(self, admin_client) -> None:
        with patch(
            "app.api.v1.admin.user_groups.AdminUserGroupService.list_groups",
            AsyncMock(return_value=[_group_row()]),
        ):
            response = admin_client.get("/api/v1/admin/user-groups/")
        assert response.status_code == 200
        body = response.json()
        assert body[0]["name"] == "外部访客"
        assert body[0]["permissions"] == ["kb"]

    def test_create_group_returns_201(self, admin_client) -> None:
        with patch(
            "app.api.v1.admin.user_groups.AdminUserGroupService.create_group",
            AsyncMock(return_value=_group_row(group_id=2, name="仅资讯")),
        ):
            response = admin_client.post(
                "/api/v1/admin/user-groups/",
                json={"name": "仅资讯", "permissions": ["news"]},
            )
        assert response.status_code == 201
        assert response.json()["name"] == "仅资讯"

    def test_create_group_unknown_permission_returns_422(self, admin_client) -> None:
        response = admin_client.post(
            "/api/v1/admin/user-groups/",
            json={"name": "坏组", "permissions": ["no-such-key"]},
        )
        assert response.status_code == 422

    def test_create_group_duplicate_name_returns_409(self, admin_client) -> None:
        with patch(
            "app.api.v1.admin.user_groups.AdminUserGroupService.create_group",
            AsyncMock(side_effect=ConflictError("用户组「外部访客」已存在")),
        ):
            response = admin_client.post(
                "/api/v1/admin/user-groups/",
                json={"name": "外部访客", "permissions": []},
            )
        assert response.status_code == 409

    def test_update_group(self, admin_client) -> None:
        updated = _group_row(permissions=["kb", "news"], is_active=False)
        with patch(
            "app.api.v1.admin.user_groups.AdminUserGroupService.update_group",
            AsyncMock(return_value=updated),
        ):
            response = admin_client.put(
                "/api/v1/admin/user-groups/1",
                json={"permissions": ["kb", "news"], "isActive": False},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["permissions"] == ["kb", "news"]
        assert body["isActive"] is False

    def test_delete_group_with_members_returns_409(self, admin_client) -> None:
        with patch(
            "app.api.v1.admin.user_groups.AdminUserGroupService.delete_group",
            AsyncMock(side_effect=ConflictError("用户组仍有 2 个成员，请先移出后再删除")),
        ):
            response = admin_client.delete("/api/v1/admin/user-groups/1")
        assert response.status_code == 409

    def test_delete_group_returns_204(self, admin_client) -> None:
        with patch(
            "app.api.v1.admin.user_groups.AdminUserGroupService.delete_group",
            AsyncMock(return_value=None),
        ):
            response = admin_client.delete("/api/v1/admin/user-groups/1")
        assert response.status_code == 204


@pytest.mark.unit
class TestFeatureGateOnRouters:
    """受限用户（未分组）直连受门控路由 → 403；admin 不受限。"""

    def test_ungrouped_user_gets_403_on_gated_router(self, client) -> None:
        stub = SimpleNamespace(id=9, username="u", role="user", is_active=True)
        app.dependency_overrides[get_current_user] = lambda: stub
        try:
            response = client.get("/api/v1/news/feed")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 403
        assert "未开通" in response.json()["detail"]

    def test_ungrouped_user_gets_401_on_gated_router_without_token(self, client) -> None:
        """门控路由同时收口匿名访问（此前 research/auction 等为匿名可达）。"""
        response = client.get("/api/v1/research/")
        assert response.status_code in (401, 403)
