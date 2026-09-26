"""交易 Agent admin 端点契约测试（复盘/交易计划查询：camelCase wire / 404 / 422）。"""

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_admin_user, get_db
from app.main import app
from app.models.agent_trading import AgentMemory, AgentTradePlan


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


def _content() -> dict:
    return {
        "period": "day",
        "trade_date": "2026-07-17",
        "overall": "整体执行纪律良好",
        "trades": [
            {
                "cl_ord_id": "A",
                "stock_code": "600000",
                "selection_verdict": "correct",
                "plan_verdict": "neutral",
                "execution_verdict": "wrong",
                "reason": "追高买入偏离计划买点",
            }
        ],
        "bias": "偏乐观",
        "suggestion": "严格执行买点纪律",
        "experiences": [
            {"title": "禁止追高", "body": "偏离买点 3% 以上不追", "mem_type": "discipline"}
        ],
    }


@pytest.mark.unit
class TestGetTradingAgentReview:
    def test_returns_camel_case_wire(self, admin_client) -> None:
        http, _ = admin_client
        row = MagicMock()
        row.structured_output = {"agent_key": "short-line", **_content()}

        with (
            patch(
                "app.services.trading.account_service.resolve_agent_account",
                AsyncMock(return_value=MagicMock(id=7)),
            ),
            patch(
                "app.repositories.review.ai_analysis_repository.load_latest_success",
                AsyncMock(return_value=row),
            ),
        ):
            resp = http.get("/api/v1/admin/trading-agent/short-line/review", params={"period": "day"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["tradeDate"] == "2026-07-17"
        assert body["trades"][0]["clOrdId"] == "A"
        assert body["trades"][0]["selectionVerdict"] == "correct"
        assert body["experiences"][0]["memType"] == "discipline"

    def test_404_when_not_generated(self, admin_client) -> None:
        http, _ = admin_client

        with (
            patch(
                "app.services.trading.account_service.resolve_agent_account",
                AsyncMock(return_value=MagicMock(id=7)),
            ),
            patch(
                "app.repositories.review.ai_analysis_repository.load_latest_success",
                AsyncMock(return_value=None),
            ),
        ):
            resp = http.get("/api/v1/admin/trading-agent/short-line/review", params={"period": "day"})

        assert resp.status_code == 404
        assert "尚未生成" in resp.json()["detail"]

    def test_422_on_unknown_period(self, admin_client) -> None:
        http, _ = admin_client

        resp = http.get(
            "/api/v1/admin/trading-agent/short-line/review", params={"period": "year"}
        )

        assert resp.status_code == 422


def _plan_row(**overrides) -> AgentTradePlan:
    fields = {
        "id": 11,
        "plan_date": date(2026, 7, 17),
        "stock_code": "600000",
        "plan_type": "buy",
        "strategy": "回踩买点区间接回",
        "buy_zone_low": Decimal("9.9000"),
        "buy_zone_high": Decimal("10.2000"),
        "target_price": Decimal("11.0000"),
        "stop_loss": Decimal("9.5000"),
        "position_pct": Decimal("10.00"),
        "status": "active",
        "selection_id": 5,
        "basis": "当日复盘解读",
        "triggered_cl_ord_id": None,
    }
    fields.update(overrides)
    return AgentTradePlan(**fields)


@pytest.mark.unit
class TestTradingAgentPlans:
    def test_list_returns_camel_case_wire(self, admin_client) -> None:
        http, _ = admin_client

        with (
            patch(
                "app.services.market.trade_calendar_service.resolve_latest_trade_date",
                AsyncMock(return_value=date(2026, 7, 17)),
            ),
            patch(
                "app.services.market.trade_calendar_service.next_trading_day",
                AsyncMock(return_value=date(2026, 7, 20)),
            ),
            patch(
                "app.services.trading.agent_plan_ops.list_plans",
                AsyncMock(return_value=[_plan_row()]),
            ),
        ):
            resp = http.get("/api/v1/admin/trading-agent/short-line/plans")

        assert resp.status_code == 200
        body = resp.json()
        assert body["tradeDate"] == "2026-07-17"
        assert body["nextTradeDate"] == "2026-07-20"
        plan = body["plans"][0]
        assert plan["planDate"] == "2026-07-17"
        assert plan["planType"] == "buy"
        assert plan["buyZoneLow"] == pytest.approx(9.9)
        assert plan["buyZoneHigh"] == pytest.approx(10.2)
        assert plan["stopLoss"] == pytest.approx(9.5)
        assert plan["positionPct"] == pytest.approx(10.0)
        assert plan["triggeredClOrdId"] is None

    def test_list_accepts_trade_date_query(self, admin_client) -> None:
        http, _ = admin_client

        with (
            patch(
                "app.services.market.trade_calendar_service.resolve_latest_trade_date",
                AsyncMock(),
            ) as resolve_mock,
            patch(
                "app.services.market.trade_calendar_service.next_trading_day",
                AsyncMock(return_value=date(2026, 7, 17)),
            ),
            patch(
                "app.services.trading.agent_plan_ops.list_plans",
                AsyncMock(return_value=[]),
            ) as list_mock,
        ):
            resp = http.get(
                "/api/v1/admin/trading-agent/short-line/plans", params={"trade_date": "2026-07-16"}
            )

        assert resp.status_code == 200
        resolve_mock.assert_not_awaited()
        assert list_mock.await_args.kwargs["plan_date"] == date(2026, 7, 16)
        body = resp.json()
        assert body["tradeDate"] == "2026-07-16"

    def test_cancel_returns_updated_plan(self, admin_client) -> None:
        http, _ = admin_client

        with patch(
            "app.services.trading.agent_plan_ops.cancel_plan",
            AsyncMock(return_value=_plan_row(status="cancelled")),
        ) as cancel_mock:
            resp = http.post("/api/v1/admin/trading-agent/short-line/plans/11/cancel")

        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"
        cancel_mock.assert_awaited_once_with(admin_client[1], "short-line", plan_id=11)


@pytest.mark.unit
class TestGetTradingAgentDates:
    def test_returns_plan_and_review_dates(self, admin_client) -> None:
        http, _ = admin_client

        with (
            patch(
                "app.services.trading.agent_plan_ops.list_plan_dates",
                AsyncMock(return_value=[date(2026, 7, 16), date(2026, 7, 17)]),
            ) as plan_dates_mock,
            patch(
                "app.services.trading.agent_review_service.list_review_dates",
                AsyncMock(side_effect=lambda _s, _k, *, period: [date(2026, 7, period == "day" and 17 or 10)]),
            ) as review_dates_mock,
        ):
            resp = http.get("/api/v1/admin/trading-agent/short-line/dates")

        assert resp.status_code == 200
        body = resp.json()
        assert body["planDates"] == ["2026-07-16", "2026-07-17"]
        assert sorted(body["reviewDates"]) == ["day", "month", "week"]
        assert body["reviewDates"]["day"] == ["2026-07-17"]
        assert body["reviewDates"]["week"] == ["2026-07-10"]
        plan_dates_mock.assert_awaited_once()
        assert review_dates_mock.await_count == 3

    def test_empty_when_no_records(self, admin_client) -> None:
        http, _ = admin_client

        with (
            patch(
                "app.services.trading.agent_plan_ops.list_plan_dates",
                AsyncMock(return_value=[]),
            ),
            patch(
                "app.services.trading.agent_review_service.list_review_dates",
                AsyncMock(return_value=[]),
            ),
        ):
            resp = http.get("/api/v1/admin/trading-agent/short-line/dates")

        assert resp.status_code == 200
        assert resp.json() == {"planDates": [], "reviewDates": {"day": [], "month": [], "week": []}}


def _group_view():
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


@pytest.mark.unit
class TestTradingAgentSelections:
    """agent 自选查询 + 人工移出（自用户自选页迁入模拟管理）。"""

    def test_get_returns_camel_case_wire(self, admin_client) -> None:
        http, _ = admin_client

        with patch(
            "app.api.v1.admin.trading_agent.agent_plan_ops.get_agent_group",
            AsyncMock(return_value=_group_view()),
        ):
            resp = http.get("/api/v1/admin/trading-agent/short-line/selections")

        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "交易 Agent"
        assert body["items"][0]["stockCode"] == "600000"
        assert body["items"][0]["reason"] == "复盘主线延续"
        assert body["items"][0]["confidence"] == pytest.approx(0.8)
        assert body["items"][0]["tradeDate"] == "2026-09-25"

    def test_get_returns_null_when_not_generated(self, admin_client) -> None:
        http, _ = admin_client

        with patch(
            "app.api.v1.admin.trading_agent.agent_plan_ops.get_agent_group",
            AsyncMock(return_value=None),
        ):
            resp = http.get("/api/v1/admin/trading-agent/short-line/selections")

        assert resp.status_code == 200
        assert resp.json() is None

    def test_get_requires_admin(self, client) -> None:
        resp = client.get("/api/v1/admin/trading-agent/short-line/selections")
        assert resp.status_code in (401, 403)

    def test_remove_selection_204(self, admin_client) -> None:
        http, session = admin_client

        with patch(
            "app.api.v1.admin.trading_agent.agent_plan_ops.remove_selection_manual",
            AsyncMock(return_value=MagicMock()),
        ) as remove_mock:
            resp = http.delete("/api/v1/admin/trading-agent/short-line/selections/9")

        assert resp.status_code == 204
        remove_mock.assert_awaited_once_with(session, "short-line", selection_id=9)

    def test_remove_selection_404(self, admin_client) -> None:
        from app.core.exceptions import NotFoundError

        http, _ = admin_client

        with patch(
            "app.api.v1.admin.trading_agent.agent_plan_ops.remove_selection_manual",
            AsyncMock(side_effect=NotFoundError("Selection not found")),
        ):
            resp = http.delete("/api/v1/admin/trading-agent/short-line/selections/99")

        assert resp.status_code == 404


def _memory_row(**overrides) -> AgentMemory:
    fields = {
        "id": 3,
        "mem_type": "discipline",
        "title": "选股本质是选板块：无板块效应不参与",
        "body": "选股必须选板块（趋势理论第一原则）",
        "source": "manual",
        "status": "active",
        "source_result_id": None,
        "created_at": datetime(2026, 9, 26, 8, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 9, 26, 8, 0, tzinfo=timezone.utc),
    }
    fields.update(overrides)
    return AgentMemory(**fields)


@pytest.mark.unit
class TestTradingAgentMemories:
    """agent 记忆管理面（方法论纪律种子 + 复盘沉淀；停用不删）。"""

    def test_list_returns_camel_case_wire(self, admin_client) -> None:
        http, _ = admin_client

        with patch(
            "app.api.v1.admin.trading_agent.agent_memory_service.list_memories",
            AsyncMock(return_value=[_memory_row()]),
        ) as list_mock:
            resp = http.get(
                "/api/v1/admin/trading-agent/short-line/memories", params={"status": "archived"}
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body[0]["memType"] == "discipline"
        assert body[0]["source"] == "manual"
        assert body[0]["sourceResultId"] is None
        assert body[0]["createdAt"] is not None
        list_mock.assert_awaited_once_with(admin_client[1], "short-line", status="archived")

    def test_list_defaults_to_all_statuses(self, admin_client) -> None:
        http, _ = admin_client

        with patch(
            "app.api.v1.admin.trading_agent.agent_memory_service.list_memories",
            AsyncMock(return_value=[]),
        ) as list_mock:
            resp = http.get("/api/v1/admin/trading-agent/short-line/memories")

        assert resp.status_code == 200
        assert resp.json() == []
        assert list_mock.await_args.kwargs["status"] is None

    def test_update_returns_edited_memory(self, admin_client) -> None:
        http, session = admin_client

        with patch(
            "app.api.v1.admin.trading_agent.agent_memory_service.update_memory",
            AsyncMock(return_value=_memory_row(title="新标题", mem_type="lesson")),
        ) as update_mock:
            resp = http.put(
                "/api/v1/admin/trading-agent/short-line/memories/3",
                json={"title": "新标题", "memType": "lesson"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "新标题"
        assert body["memType"] == "lesson"
        update_mock.assert_awaited_once_with(
            session, "short-line", memory_id=3, title="新标题", body=None, mem_type="lesson"
        )

    def test_update_status_switches_active_archived(self, admin_client) -> None:
        http, session = admin_client

        with patch(
            "app.api.v1.admin.trading_agent.agent_memory_service.update_memory_status",
            AsyncMock(return_value=_memory_row(status="archived")),
        ) as status_mock:
            resp = http.put(
                "/api/v1/admin/trading-agent/short-line/memories/3/status",
                json={"status": "archived"},
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"
        status_mock.assert_awaited_once_with(session, "short-line", memory_id=3, status="archived")

    def test_update_rejects_unknown_mem_type(self, admin_client) -> None:
        http, _ = admin_client

        resp = http.put(
            "/api/v1/admin/trading-agent/short-line/memories/3", json={"memType": "other"}
        )

        assert resp.status_code == 422

    def test_update_404_when_missing(self, admin_client) -> None:
        from app.core.exceptions import NotFoundError

        http, _ = admin_client

        with patch(
            "app.api.v1.admin.trading_agent.agent_memory_service.update_memory",
            AsyncMock(side_effect=NotFoundError("记忆 99 不存在")),
        ):
            resp = http.put(
                "/api/v1/admin/trading-agent/short-line/memories/99", json={"title": "x"}
            )

        assert resp.status_code == 404
