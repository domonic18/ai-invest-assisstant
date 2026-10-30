"""MCP 自选股工具测试（读写 scope 门禁 / 参数校验 / 服务层复用）。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.server.auth.provider import AccessToken
from mcp.server.fastmcp.exceptions import ToolError

from app.api.v1.mcp import tools as mcp_tools
from app.core.exceptions import BadRequestError
from app.schemas.user import WatchlistBatchResponse

pytestmark = pytest.mark.unit

WATCHLIST_SERVICE = "app.services.user.watchlist_service.WatchlistService"


def _token(scopes: list[str], user_id: int = 7) -> AccessToken:
    return AccessToken(
        token="inv_test",
        client_id=f"user:{user_id}",
        scopes=scopes,
        claims={"user_id": user_id},
    )


def _auth(scopes: list[str]) -> str:
    return patch.object(mcp_tools, "get_access_token", return_value=_token(scopes))


def _session_ctx() -> tuple[MagicMock, AsyncMock]:
    session = AsyncMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx, session


def _run(coro):
    import asyncio

    return asyncio.run(coro)


def _group(name: str = "默认分组", *, is_default: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        name=name,
        is_default=is_default,
        ai_review_enabled=False,
        items=[],
    )


def test_watchlist_read_requires_read_scope():
    with _auth(["watchlist:write"]):
        with pytest.raises(ToolError, match="watchlist:read"):
            mcp_tools._require_scope("watchlist:read")


def test_watchlist_write_requires_write_scope():
    with _auth(["watchlist:read"]):
        with pytest.raises(ToolError, match="watchlist:write"):
            mcp_tools._require_scope("watchlist:write")


def test_list_groups_returns_counts():
    ctx, _ = _session_ctx()
    with _auth(["watchlist:read"]), patch.object(
        mcp_tools, "AsyncSessionLocal", return_value=ctx
    ), patch(WATCHLIST_SERVICE) as service_cls:
        service_cls.return_value.list_groups_with_items = AsyncMock(
            return_value=[_group()]
        )
        result = _run(mcp_tools.list_watchlist_groups())

    assert result == {
        "groups": [
            {
                "id": 1,
                "name": "默认分组",
                "is_default": True,
                "ai_review_enabled": False,
                "stock_count": 0,
            }
        ]
    }


def test_get_watchlist_filters_by_group_name():
    ctx, session = _session_ctx()
    item = SimpleNamespace(
        stock_code="600519",
        market="sh",
        group_id=1,
        created_at=MagicMock(),
    )
    group = _group("日周60", is_default=False)
    group.items = [item]
    with _auth(["watchlist:read"]), patch.object(
        mcp_tools, "AsyncSessionLocal", return_value=ctx
    ), patch(WATCHLIST_SERVICE) as service_cls, patch(
        "app.repositories.market.stock_repository.StockRepository"
    ) as stock_repo_cls:
        session.execute = AsyncMock()
        service_cls.return_value.list_groups_with_items = AsyncMock(return_value=[group])
        stock_repo_cls.return_value.get_names_by_codes = AsyncMock(
            return_value={"600519": "贵州茅台"}
        )
        result = _run(mcp_tools.get_watchlist("日周60"))

    assert result["groups"][0]["name"] == "日周60"
    assert result["groups"][0]["stocks"][0]["stock_name"] == "贵州茅台"


def test_get_watchlist_missing_group_returns_hint():
    ctx, _ = _session_ctx()
    with _auth(["watchlist:read"]), patch.object(
        mcp_tools, "AsyncSessionLocal", return_value=ctx
    ), patch(WATCHLIST_SERVICE) as service_cls, patch(
        "app.repositories.market.stock_repository.StockRepository"
    ) as stock_repo_cls:
        service_cls.return_value.list_groups_with_items = AsyncMock(
            return_value=[_group()]
        )
        stock_repo_cls.return_value.get_names_by_codes = AsyncMock(return_value={})
        result = _run(mcp_tools.get_watchlist("不存在"))

    assert result["groups"] == []
    assert "默认分组" in result["hint"]


def test_add_stocks_rejects_empty_and_conflicting_params():
    with _auth(["watchlist:write"]):
        assert "error" in _run(mcp_tools.add_watchlist_stocks([]))
        assert "error" in _run(
            mcp_tools.add_watchlist_stocks(["600519"], "A", "B")
        )


def test_add_stocks_reports_unknown_group():
    ctx, _ = _session_ctx()
    with _auth(["watchlist:write"]), patch.object(
        mcp_tools, "AsyncSessionLocal", return_value=ctx
    ), patch(WATCHLIST_SERVICE) as service_cls:
        service_cls.return_value.get_group_by_name = AsyncMock(return_value=None)
        service_cls.return_value.list_groups_with_items = AsyncMock(
            return_value=[_group()]
        )
        result = _run(mcp_tools.add_watchlist_stocks(["600519"], group_name="X"))

    assert result["available_groups"] == ["默认分组"]


def test_add_stocks_delegates_batch_with_user_id():
    ctx, session = _session_ctx()
    session.get = AsyncMock(return_value=SimpleNamespace(id=7))
    with _auth(["watchlist:write"]), patch.object(
        mcp_tools, "AsyncSessionLocal", return_value=ctx
    ), patch(WATCHLIST_SERVICE) as service_cls:
        batch = AsyncMock(return_value=WatchlistBatchResponse())
        service_cls.return_value.batch_add_items = batch
        result = _run(mcp_tools.add_watchlist_stocks(["600519", "600519"]))

    _, payload = batch.await_args.args
    assert [item.stock_code for item in payload.items] == ["600519"]
    assert result == {"created": [], "duplicated": [], "invalid": []}


def test_add_stocks_maps_app_error_to_payload():
    ctx, session = _session_ctx()
    session.get = AsyncMock(return_value=SimpleNamespace(id=7))
    with _auth(["watchlist:write"]), patch.object(
        mcp_tools, "AsyncSessionLocal", return_value=ctx
    ), patch(WATCHLIST_SERVICE) as service_cls:
        service_cls.return_value.batch_add_items = AsyncMock(
            side_effect=BadRequestError("Group limit reached (20)")
        )
        result = _run(mcp_tools.add_watchlist_stocks(["600519"]))

    assert result == {"error": "Group limit reached (20)"}


def test_remove_stocks_delegates_and_returns_categories():
    ctx, _ = _session_ctx()
    with _auth(["watchlist:write"]), patch.object(
        mcp_tools, "AsyncSessionLocal", return_value=ctx
    ), patch(WATCHLIST_SERVICE) as service_cls:
        service_cls.return_value.remove_watchlist_stocks = AsyncMock(
            return_value={"removed": ["600519"], "not_found": [], "mismatch": []}
        )
        result = _run(mcp_tools.remove_watchlist_stocks(["600519"]))

    assert result["removed"] == ["600519"]


def test_move_stock_reports_missing_target():
    ctx, _ = _session_ctx()
    with _auth(["watchlist:write"]), patch.object(
        mcp_tools, "AsyncSessionLocal", return_value=ctx
    ), patch(WATCHLIST_SERVICE) as service_cls:
        service_cls.return_value.get_group_by_name = AsyncMock(return_value=None)
        service_cls.return_value.list_groups_with_items = AsyncMock(
            return_value=[_group()]
        )
        result = _run(mcp_tools.move_watchlist_stock("600519", "X"))

    assert "未找到分组" in result["error"]


def test_move_stock_reports_missing_item():
    ctx, _ = _session_ctx()
    with _auth(["watchlist:write"]), patch.object(
        mcp_tools, "AsyncSessionLocal", return_value=ctx
    ), patch(WATCHLIST_SERVICE) as service_cls:
        service_cls.return_value.get_group_by_name = AsyncMock(return_value=_group())
        service_cls.return_value.get_item_by_stock_code = AsyncMock(return_value=None)
        result = _run(mcp_tools.move_watchlist_stock("600519", "默认分组"))

    assert "不存在" in result["error"]


def test_move_stock_returns_new_group():
    ctx, _ = _session_ctx()
    target = _group("日周60", is_default=False)
    item = SimpleNamespace(id=5, stock_code="600519", group_id=1)
    with _auth(["watchlist:write"]), patch.object(
        mcp_tools, "AsyncSessionLocal", return_value=ctx
    ), patch(WATCHLIST_SERVICE) as service_cls:
        service_cls.return_value.get_group_by_name = AsyncMock(return_value=target)
        service_cls.return_value.get_item_by_stock_code = AsyncMock(return_value=item)
        service_cls.return_value.move_watchlist_item = AsyncMock(
            return_value=SimpleNamespace(stock_code="600519", group_id=2)
        )
        result = _run(mcp_tools.move_watchlist_stock("600519", "日周60"))

    assert result == {
        "stock_code": "600519",
        "group_id": 2,
        "group_name": "日周60",
        "previous_group_id": 1,
    }


def test_manage_group_validates_action():
    with _auth(["watchlist:write"]):
        assert "error" in _run(mcp_tools.manage_watchlist_group("drop", "x"))
        assert "error" in _run(mcp_tools.manage_watchlist_group("rename", "x"))


def test_manage_group_create_returns_payload():
    ctx, _ = _session_ctx()
    with _auth(["watchlist:write"]), patch.object(
        mcp_tools, "AsyncSessionLocal", return_value=ctx
    ), patch(WATCHLIST_SERVICE) as service_cls:
        service_cls.return_value.create_group = AsyncMock(return_value=_group("新组", is_default=False))
        result = _run(mcp_tools.manage_watchlist_group("create", "新组"))

    assert result["action"] == "create"
    assert result["group"]["name"] == "新组"


def test_manage_group_delete_maps_service_error():
    ctx, _ = _session_ctx()
    with _auth(["watchlist:write"]), patch.object(
        mcp_tools, "AsyncSessionLocal", return_value=ctx
    ), patch(WATCHLIST_SERVICE) as service_cls:
        service_cls.return_value.get_group_by_name = AsyncMock(return_value=_group())
        service_cls.return_value.delete_group = AsyncMock(
            side_effect=BadRequestError("Default group cannot be deleted")
        )
        result = _run(mcp_tools.manage_watchlist_group("delete", "默认分组"))

    assert result == {"error": "Default group cannot be deleted"}


def test_register_tools_exposes_fifteen_tools():
    mcp = MagicMock()
    mcp_tools.register_tools(mcp)
    assert mcp.add_tool.call_count == 15
