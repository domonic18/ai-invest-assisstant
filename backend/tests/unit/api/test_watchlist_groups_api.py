"""自选股分组端点契约测试（鉴权 / CRUD / 错误码）。"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.dependencies import get_current_user
from app.main import app


@pytest.fixture
def user():
    return type(
        "User",
        (object,),
        {"id": 1, "username": "user", "role": "user", "is_active": True},
    )()


@pytest.fixture
def auth_client(client, user):
    app.dependency_overrides[get_current_user] = lambda: user
    yield client
    app.dependency_overrides.clear()


def _make_group(
    group_id: int,
    *,
    name: str = "科技",
    sort_order: int = 0,
    is_default: bool = False,
) -> type:
    group = type(
        "Group",
        (object,),
        {
            "id": group_id,
            "name": name,
            "sort_order": sort_order,
            "is_default": is_default,
            "ai_review_enabled": False,
            "created_at": datetime(2026, 9, 2, tzinfo=timezone.utc),
            "items": [],
        },
    )()
    return group


def _make_item(item_id: int, group_id: int) -> type:
    return type(
        "Item",
        (object,),
        {
            "id": item_id,
            "stock_code": "600519",
            "tags": None,
            "group_id": group_id,
            "created_at": datetime(2026, 9, 2, tzinfo=timezone.utc),
        },
    )()


@pytest.mark.unit
class TestWatchlistGroupsApi:
    def test_list_groups_returns_tree(self, auth_client) -> None:
        default_group = _make_group(7, name="默认分组", is_default=True)
        default_group.items = [_make_item(11, 7)]
        tech_group = _make_group(8)
        with patch(
            "app.api.v1.users.WatchlistService"
        ) as service_cls:
            service_cls.return_value.list_groups_with_items = AsyncMock(
                return_value=[default_group, tech_group]
            )
            resp = auth_client.get("/api/v1/users/watchlist/groups")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert body[0]["is_default"] is True
        assert body[0]["items"][0]["stock_code"] == "600519"
        assert body[1]["items"] == []

    def test_create_group_conflict_on_limit(self, auth_client) -> None:
        with patch("app.api.v1.users.WatchlistService") as service_cls:
            from app.services.user.watchlist_service import GroupLimitError

            service_cls.return_value.create_group = AsyncMock(
                side_effect=GroupLimitError("Group limit reached (20)")
            )
            resp = auth_client.post(
                "/api/v1/users/watchlist/groups",
                json={"name": "新组"},
            )

        assert resp.status_code == 409

    def test_create_group_duplicate_name_400(self, auth_client) -> None:
        with patch("app.api.v1.users.WatchlistService") as service_cls:
            service_cls.return_value.create_group = AsyncMock(
                side_effect=ValueError("Group name already exists")
            )
            resp = auth_client.post(
                "/api/v1/users/watchlist/groups",
                json={"name": "科技"},
            )

        assert resp.status_code == 400

    def test_update_group_missing_404(self, auth_client) -> None:
        with patch("app.api.v1.users.WatchlistService") as service_cls:
            service_cls.return_value.update_group = AsyncMock(
                side_effect=LookupError("Group not found")
            )
            resp = auth_client.patch(
                "/api/v1/users/watchlist/groups/999",
                json={"name": "改名"},
            )

        assert resp.status_code == 404

    def test_delete_group_204(self, auth_client) -> None:
        with patch("app.api.v1.users.WatchlistService") as service_cls:
            service_cls.return_value.delete_group = AsyncMock(return_value=None)
            resp = auth_client.delete("/api/v1/users/watchlist/groups/8")

        assert resp.status_code == 204

    def test_reorder_mismatch_400(self, auth_client) -> None:
        with patch("app.api.v1.users.WatchlistService") as service_cls:
            service_cls.return_value.reorder_groups = AsyncMock(
                side_effect=ValueError("Group id list does not match user groups")
            )
            resp = auth_client.put(
                "/api/v1/users/watchlist/groups/order",
                json={"group_ids": [7]},
            )

        assert resp.status_code == 400

    def test_move_item_missing_404(self, auth_client) -> None:
        with patch("app.api.v1.users.WatchlistService") as service_cls:
            service_cls.return_value.move_watchlist_item = AsyncMock(
                side_effect=LookupError("Watchlist item not found")
            )
            resp = auth_client.patch(
                "/api/v1/users/watchlist/items/999",
                json={"group_id": 8},
            )

        assert resp.status_code == 404

    def test_delete_item_204(self, auth_client) -> None:
        with patch("app.api.v1.users.WatchlistService") as service_cls:
            service_cls.return_value.remove_watchlist_item = AsyncMock(return_value=None)
            resp = auth_client.delete("/api/v1/users/watchlist/items/11")

        assert resp.status_code == 204

    def test_requires_auth(self, client) -> None:
        resp = client.get("/api/v1/users/watchlist/groups")
        assert resp.status_code in (401, 403)
