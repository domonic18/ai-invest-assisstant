"""自选股分组端点契约测试（鉴权 / CRUD / 错误码 / agent 分组）。"""

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import BadRequestError, NotFoundError
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
        assert body[0]["isDefault"] is True
        assert body[0]["items"][0]["stockCode"] == "600519"
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
                side_effect=BadRequestError("Group name already exists")
            )
            resp = auth_client.post(
                "/api/v1/users/watchlist/groups",
                json={"name": "科技"},
            )

        assert resp.status_code == 400

    def test_update_group_missing_404(self, auth_client) -> None:
        with patch("app.api.v1.users.WatchlistService") as service_cls:
            service_cls.return_value.update_group = AsyncMock(
                side_effect=NotFoundError("Group not found")
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
        # 缺省移入默认分组
        service_cls.return_value.delete_group.assert_awaited_once_with(
            1, 8, delete_items=False
        )

    def test_delete_group_delete_items_true(self, auth_client) -> None:
        with patch("app.api.v1.users.WatchlistService") as service_cls:
            service_cls.return_value.delete_group = AsyncMock(return_value=None)
            resp = auth_client.delete("/api/v1/users/watchlist/groups/8?delete_items=true")

        assert resp.status_code == 204
        service_cls.return_value.delete_group.assert_awaited_once_with(
            1, 8, delete_items=True
        )

    def test_reorder_mismatch_400(self, auth_client) -> None:
        with patch("app.api.v1.users.WatchlistService") as service_cls:
            service_cls.return_value.reorder_groups = AsyncMock(
                side_effect=BadRequestError("Group id list does not match user groups")
            )
            resp = auth_client.put(
                "/api/v1/users/watchlist/groups/order",
                json={"group_ids": [7]},
            )

        assert resp.status_code == 400

    def test_move_item_missing_404(self, auth_client) -> None:
        with patch("app.api.v1.users.WatchlistService") as service_cls:
            service_cls.return_value.move_watchlist_item = AsyncMock(
                side_effect=NotFoundError("Watchlist item not found")
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


@pytest.mark.unit
class TestAgentWatchlistGroupApi:
    """平台 agent 分组（全员可见）+ 人工移出（全局生效）端点。"""

    def _group_view(self):
        from app.models.agent_trading import AgentStockSelection
        from app.models.watchlist import UserWatchlistGroup
        from app.services.trading.agent_plan_ops import AgentGroupView

        group = UserWatchlistGroup(
            id=5,
            user_id=None,
            owner_type="agent",
            name="交易 Agent",
            sort_order=999,
            is_default=False,
            ai_review_enabled=False,
        )
        selection = AgentStockSelection(
            id=9,
            trade_date=date(2026, 9, 25),
            stock_code="600000",
            reason="复盘主线延续",
            confidence=Decimal("0.8000"),
            status="active",
        )
        return AgentGroupView(group=group, selections=[selection])

    def test_returns_group_with_selections(self, auth_client) -> None:
        from app.services.trading.agent_plan_ops import AgentGroupView

        view: AgentGroupView = self._group_view()
        with patch(
            "app.api.v1.users.agent_plan_ops.get_agent_group",
            AsyncMock(return_value=view),
        ):
            resp = auth_client.get("/api/v1/users/watchlist/agent-group")

        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "交易 Agent"
        assert body["items"][0]["stockCode"] == "600000"
        assert body["items"][0]["reason"] == "复盘主线延续"
        assert body["items"][0]["confidence"] == pytest.approx(0.8)
        assert body["items"][0]["tradeDate"] == "2026-09-25"

    def test_returns_null_when_not_generated(self, auth_client) -> None:
        with patch(
            "app.api.v1.users.agent_plan_ops.get_agent_group",
            AsyncMock(return_value=None),
        ):
            resp = auth_client.get("/api/v1/users/watchlist/agent-group")

        assert resp.status_code == 200
        assert resp.json() is None

    def test_remove_selection_204(self, auth_client) -> None:
        with patch(
            "app.api.v1.users.agent_plan_ops.remove_selection_manual",
            AsyncMock(return_value=MagicMock()),
        ) as remove_mock:
            resp = auth_client.delete("/api/v1/users/watchlist/agent-group/selections/9")

        assert resp.status_code == 204
        remove_mock.assert_awaited_once()

    def test_remove_selection_404(self, auth_client) -> None:
        from app.core.exceptions import NotFoundError

        with patch(
            "app.api.v1.users.agent_plan_ops.remove_selection_manual",
            AsyncMock(side_effect=NotFoundError("Selection not found")),
        ):
            resp = auth_client.delete("/api/v1/users/watchlist/agent-group/selections/99")

        assert resp.status_code == 404
