"""MCP 只读工具测试（Scope 门禁 / 参数解析 / 服务层复用与输出裁剪）。"""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.server.auth.provider import AccessToken
from mcp.server.fastmcp.exceptions import ToolError

from app.api.v1.mcp import tools as mcp_tools

pytestmark = pytest.mark.unit


def _token(scopes: list[str], user_id: int = 7) -> AccessToken:
    return AccessToken(
        token="inv_test",
        client_id=f"user:{user_id}",
        scopes=scopes,
        claims={"user_id": user_id},
    )


def _auth(scopes: list[str]) -> str:
    return patch.object(mcp_tools, "get_access_token", return_value=_token(scopes))


def _session_ctx() -> MagicMock:
    session = AsyncMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


def _run(coro):
    import asyncio

    return asyncio.run(coro)


def test_require_scope_rejects_missing_token():
    with patch.object(mcp_tools, "get_access_token", return_value=None):
        with pytest.raises(ToolError, match="缺少有效身份"):
            mcp_tools._require_scope("market:read")


def test_require_scope_rejects_missing_scope():
    with _auth(["kb:read"]):
        with pytest.raises(ToolError, match="market:read"):
            mcp_tools._require_scope("market:read")


def test_invalid_date_returns_error_payload():
    with _auth(["market:read"]):
        result = _run(mcp_tools.get_market_daily_review("2026-13-01"))

    assert result["error"].startswith("无效的 trade_date")


def test_market_review_none_returns_not_ready():
    with _auth(["market:read"]), patch.object(
        mcp_tools, "AsyncSessionLocal", return_value=_session_ctx()
    ), patch(
        "app.services.review.market_review_service.get_market_review",
        AsyncMock(return_value=None),
    ):
        result = _run(mcp_tools.get_market_daily_review("2026-10-29"))

    assert result == {
        "trade_date": "2026-10-29",
        "not_ready": True,
        "note": "该交易日大盘复盘尚未生成（盘后定时任务生成，或等待数据就绪）。",
    }


def test_market_review_passes_user_scope_to_service():
    review = MagicMock()
    review.model_dump.return_value = {"trade_date": "2026-10-29", "summary": "ok"}
    mocked = AsyncMock(return_value=review)
    with _auth(["market:read"]), patch.object(
        mcp_tools, "AsyncSessionLocal", return_value=_session_ctx()
    ), patch("app.services.review.market_review_service.get_market_review", mocked):
        result = _run(mcp_tools.get_market_daily_review("2026-10-29"))

    assert result["summary"] == "ok"
    assert mocked.await_args.args[1] == 7
    assert mocked.await_args.args[2] == date(2026, 10, 29)


def _board(count: int, items_key: str = "items") -> MagicMock:
    board = MagicMock()
    board.items = [object()] * count
    board.model_dump.return_value = {items_key: [{"code": i} for i in range(count)]}
    return board


def test_sector_anomaly_slices_items_to_limit():
    board = _board(30)
    with _auth(["market:read"]), patch.object(
        mcp_tools, "AsyncSessionLocal", return_value=_session_ctx()
    ), patch(
        "app.services.market.sector_anomaly_service.get_sector_anomaly_board",
        AsyncMock(return_value=board),
    ):
        result = _run(mcp_tools.get_sector_anomaly(limit=5))

    assert result["returned"] == 5
    assert len(result["items"]) == 5


def test_sector_anomaly_empty_returns_note():
    with _auth(["market:read"]), patch.object(
        mcp_tools, "AsyncSessionLocal", return_value=_session_ctx()
    ), patch(
        "app.services.market.sector_anomaly_service.get_sector_anomaly_board",
        AsyncMock(return_value=None),
    ):
        result = _run(mcp_tools.get_sector_anomaly())

    assert result["items"] == []
    assert "note" in result


def test_stock_anomaly_passes_user_id():
    board = _board(3)
    mocked = AsyncMock(return_value=board)
    with _auth(["market:read"]), patch.object(
        mcp_tools, "AsyncSessionLocal", return_value=_session_ctx()
    ), patch(
        "app.services.market.stock_anomaly_service.get_stock_anomaly_board", mocked
    ):
        _run(mcp_tools.get_stock_anomaly("2026-10-29", limit=10))

    assert mocked.await_args.args[1] == date(2026, 10, 29)
    assert mocked.await_args.args[2] == 7


def test_social_sentiment_resolves_latest_trade_date():
    resolve = AsyncMock(return_value=date(2026, 10, 29))
    sentiment = AsyncMock(return_value={"trade_date": "2026-10-29"})
    with _auth(["market:read"]), patch.object(
        mcp_tools, "AsyncSessionLocal", return_value=_session_ctx()
    ), patch(
        "app.services.market.trade_calendar_service.resolve_latest_trade_date", resolve
    ), patch("app.services.social.feed_service.get_review_sentiment", sentiment):
        result = _run(mcp_tools.get_social_sentiment())

    assert result["trade_date"] == "2026-10-29"
    assert sentiment.await_args.args[1] == date(2026, 10, 29)


def test_trading_account_uses_default_agent_and_returns_error_on_app_error():
    from app.core.exceptions import NotFoundError

    with _auth(["trading:read"]), patch.object(
        mcp_tools, "AsyncSessionLocal", return_value=_session_ctx()
    ), patch(
        "app.services.trading.account_service.resolve_agent_account",
        AsyncMock(side_effect=NotFoundError("agent 不存在")),
    ):
        result = _run(mcp_tools.get_trading_account())

    assert result == {"error": "agent 不存在"}


def test_trading_account_returns_overview():
    account = SimpleNamespace()
    overview = AsyncMock(return_value={"total_asset": 100000.0})
    resolve = AsyncMock(return_value=account)
    with _auth(["trading:read"]), patch.object(
        mcp_tools, "AsyncSessionLocal", return_value=_session_ctx()
    ), patch("app.services.trading.account_service.resolve_agent_account", resolve), patch(
        "app.services.trading.paper_trade_service.get_overview", overview
    ):
        result = _run(mcp_tools.get_trading_account("long-line"))

    assert result["total_asset"] == 100000.0
    assert resolve.await_args.args[1] == "long-line"


def test_trading_review_rejects_invalid_scope_and_period():
    with _auth(["trading:read"]):
        assert "scope" in _run(mcp_tools.get_trading_review(scope="all"))["error"]
        assert "period" in _run(mcp_tools.get_trading_review(period="week2"))["error"]


def test_trading_review_requires_paired_custom_range():
    with _auth(["trading:read"]):
        result = _run(mcp_tools.get_trading_review(start_date="2026-10-01"))

    assert result == {"error": "自定义区间须同时提供 start_date 与 end_date"}


def test_trading_review_passes_custom_range():
    content = MagicMock()
    content.model_dump.return_value = {"period": "custom"}
    mocked = AsyncMock(return_value=content)
    with _auth(["trading:read"]), patch.object(
        mcp_tools, "AsyncSessionLocal", return_value=_session_ctx()
    ), patch("app.services.trading.agent_review_service.get_review", mocked):
        result = _run(
            mcp_tools.get_trading_review(
                start_date="2026-10-01", end_date="2026-10-20"
            )
        )

    assert result["period"] == "custom"
    kwargs = mocked.await_args.kwargs
    assert kwargs["period"] is None
    assert kwargs["start_date"] == date(2026, 10, 1)
    assert kwargs["end_date"] == date(2026, 10, 20)


def test_list_trading_plans_serializes_decimals():
    from decimal import Decimal

    row = SimpleNamespace(
        id=1,
        stock_code="600000",
        plan_type="buy",
        strategy="突破",
        buy_zone_low=Decimal("10.1"),
        buy_zone_high=None,
        target_price=Decimal("11.5"),
        stop_loss=Decimal("9.5"),
        position_pct=Decimal("10"),
        status="pending",
        triggered_cl_ord_id=None,
    )
    with _auth(["trading:read"]), patch.object(
        mcp_tools, "AsyncSessionLocal", return_value=_session_ctx()
    ), patch(
        "app.services.trading.agent_registry.get_agent", AsyncMock()
    ), patch(
        "app.services.trading.agent_plan_ops.resolve_default_plan_date",
        AsyncMock(return_value=date(2026, 10, 29)),
    ), patch(
        "app.services.trading.agent_plan_ops.list_plans", AsyncMock(return_value=[row])
    ):
        result = _run(mcp_tools.list_trading_plans())

    item = result["items"][0]
    assert result["trade_date"] == "2026-10-29"
    assert item["buy_zone_low"] == 10.1
    assert item["buy_zone_high"] is None
    assert item["target_price"] == 11.5


def test_search_knowledge_base_delegates_to_shared_impl():
    mocked = AsyncMock(return_value={"points": [], "segments": []})
    with _auth(["kb:read"]), patch(
        "app.agent.tools.kb_tools.search_knowledge_base_data", mocked
    ):
        result = _run(mcp_tools.search_knowledge_base("均线金叉", include_media=True))

    assert result["points"] == []
    assert mocked.await_args.args == ("均线金叉", None, None, None, True)


def test_all_tools_registered():
    mcp = MagicMock()
    mcp_tools.register_tools(mcp)

    names = [call.args[0].__name__ for call in mcp.add_tool.call_args_list]
    assert names == [
        "get_market_daily_review",
        "get_sector_anomaly",
        "get_stock_anomaly",
        "get_social_sentiment",
        "get_trading_account",
        "list_trading_plans",
        "get_trading_review",
        "get_trading_selections",
        "search_knowledge_base",
    ]
