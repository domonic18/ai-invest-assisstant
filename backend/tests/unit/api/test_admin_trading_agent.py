"""交易 Agent admin 端点契约测试（复盘/交易计划查询：camelCase wire / 404 / 422）。"""

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import NotFoundError
from app.dependencies import get_current_admin_user, get_db
from app.main import app
from app.models.agent_trading import AgentMemory, AgentTradePlan
from app.schemas.paper_trade import (
    AgentCapabilityResponse,
    TradingAgentObservationDecision,
    TradingAgentObservationItem,
    TradingAgentObservationPage,
    TradingAgentObservationSummary,
    TradingAgentPlanAmendmentResponse,
    TradingAgentPlanResponse,
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
        "no_target_reason": None,
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
        assert body["noTargetReason"] is None

    def test_returns_no_target_reason_for_idle_review(self, admin_client) -> None:
        """空仓无复盘对象标记行：noTargetReason 透出供前端与「未生成」区分。"""
        http, _ = admin_client
        row = MagicMock()
        row.structured_output = {
            "agent_key": "short-line",
            **_content(),
            "overall": "",
            "trades": [],
            "bias": "",
            "suggestion": "",
            "no_target_reason": "复盘窗口内无委托成交，账户亦无历史持仓（空仓无复盘对象）",
        }

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
        assert (
            resp.json()["noTargetReason"]
            == "复盘窗口内无委托成交，账户亦无历史持仓（空仓无复盘对象）"
        )

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
        "version": 1,
        "triggered_cl_ord_id": None,
    }
    fields.update(overrides)
    return AgentTradePlan(**fields)


def _plan_view(**overrides: object) -> TradingAgentPlanResponse:
    view = TradingAgentPlanResponse.model_validate(_plan_row(**overrides))
    return view


@pytest.mark.unit
class TestTradingAgentPlans:
    def test_list_returns_camel_case_wire(self, admin_client) -> None:
        http, _ = admin_client
        view = _plan_view()
        view.stock_name = "浦发银行"

        with (
            patch(
                "app.services.trading.agent_plan_ops.resolve_default_plan_date",
                AsyncMock(return_value=date(2026, 7, 17)),
            ),
            patch(
                "app.services.trading.agent_plan_ops.resolve_executing_plan_date",
                AsyncMock(return_value=None),
            ),
            patch(
                "app.services.market.trade_calendar_service.next_trading_day",
                AsyncMock(return_value=date(2026, 7, 20)),
            ),
            patch(
                "app.services.trading.agent_plan_ops.list_plan_views",
                AsyncMock(return_value=[view]),
            ),
            patch(
                "app.services.trading.agent_plan_ops.list_amendment_views",
                AsyncMock(
                    return_value=[
                        TradingAgentPlanAmendmentResponse(
                            plan_date=date(2026, 7, 17),
                            window="1020",
                            stock_code="600000",
                            plan_id=11,
                            action="adjust",
                            reason="早盘放量，止损上移",
                            new_buy_zone_low=None,
                            new_buy_zone_high=None,
                            new_target_price=None,
                            new_stop_loss=9.8,
                            new_position_pct=None,
                            status="shadow",
                            reject_reason=None,
                            new_plan_id=None,
                            model_name="kimi-k2",
                            created_at=datetime(2026, 7, 17, 2, 20, tzinfo=timezone.utc),
                        )
                    ]
                ),
            ),
            patch(
                "app.services.trading.agent_plan_service.load_plan_content_for_date",
                AsyncMock(return_value=MagicMock(stand_aside_reason=None)),
            ),
        ):
            resp = http.get("/api/v1/admin/trading-agent/short-line/plans")

        assert resp.status_code == 200
        body = resp.json()
        assert body["tradeDate"] == "2026-07-17"
        assert body["nextTradeDate"] == "2026-07-20"
        assert body["standAsideReason"] is None
        assert body["executingPlanDate"] is None
        amendment = body["amendments"][0]
        assert amendment["window"] == "1020"
        assert amendment["action"] == "adjust"
        assert amendment["status"] == "shadow"
        assert amendment["newStopLoss"] == pytest.approx(9.8)
        assert amendment["modelName"] == "kimi-k2"
        plan = body["plans"][0]
        assert plan["stockCode"] == "600000"
        assert plan["stockName"] == "浦发银行"
        assert plan["planDate"] == "2026-07-17"
        assert plan["planType"] == "buy"
        assert plan["buyZoneLow"] == pytest.approx(9.9)
        assert plan["buyZoneHigh"] == pytest.approx(10.2)
        assert plan["stopLoss"] == pytest.approx(9.5)
        assert plan["positionPct"] == pytest.approx(10.0)
        assert plan["triggeredClOrdId"] is None

    def test_list_returns_stand_aside_reason_when_no_plans(self, admin_client) -> None:
        """三态契约：plans 空 + 原因非空 = 已生成但空仓观望（区别于未生成）。"""
        http, _ = admin_client

        with (
            patch(
                "app.services.trading.agent_plan_ops.resolve_default_plan_date",
                AsyncMock(return_value=date(2026, 7, 17)),
            ),
            patch(
                "app.services.trading.agent_plan_ops.resolve_executing_plan_date",
                AsyncMock(return_value=None),
            ),
            patch(
                "app.services.market.trade_calendar_service.next_trading_day",
                AsyncMock(return_value=date(2026, 7, 20)),
            ),
            patch(
                "app.services.trading.agent_plan_ops.list_plan_views",
                AsyncMock(return_value=[]),
            ),
            patch(
                "app.services.trading.agent_plan_service.load_plan_content_for_date",
                AsyncMock(return_value=MagicMock(stand_aside_reason="大盘系统性风险，空仓观望")),
            ),
        ):
            resp = http.get("/api/v1/admin/trading-agent/short-line/plans")

        assert resp.status_code == 200
        body = resp.json()
        assert body["plans"] == []
        assert body["standAsideReason"] == "大盘系统性风险，空仓观望"

    def test_list_accepts_trade_date_query(self, admin_client) -> None:
        http, _ = admin_client

        with (
            patch(
                "app.services.trading.agent_plan_ops.resolve_default_plan_date",
                AsyncMock(),
            ) as default_resolve_mock,
            patch(
                "app.services.trading.agent_plan_ops.resolve_executing_plan_date",
                AsyncMock(return_value=None),
            ),
            patch(
                "app.services.market.trade_calendar_service.next_trading_day",
                AsyncMock(return_value=date(2026, 7, 17)),
            ),
            patch(
                "app.services.trading.agent_plan_ops.list_plan_views",
                AsyncMock(return_value=[]),
            ) as list_mock,
            patch(
                "app.services.trading.agent_plan_service.load_plan_content_for_date",
                AsyncMock(return_value=None),
            ),
        ):
            resp = http.get(
                "/api/v1/admin/trading-agent/short-line/plans", params={"trade_date": "2026-07-16"}
            )

        assert resp.status_code == 200
        default_resolve_mock.assert_not_awaited()
        assert list_mock.await_args.kwargs["plan_date"] == date(2026, 7, 16)
        body = resp.json()
        assert body["tradeDate"] == "2026-07-16"
        assert body["standAsideReason"] is None

    def test_list_surfaces_executing_plan_date(self, admin_client) -> None:
        """所选日盘中执行的计划集制定日透出（空态引导跳转数据源）。"""
        http, _ = admin_client

        with (
            patch(
                "app.services.trading.agent_plan_ops.resolve_default_plan_date",
                AsyncMock(return_value=date(2026, 7, 17)),
            ),
            patch(
                "app.services.trading.agent_plan_ops.resolve_executing_plan_date",
                AsyncMock(return_value=date(2026, 7, 16)),
            ),
            patch(
                "app.services.market.trade_calendar_service.next_trading_day",
                AsyncMock(return_value=date(2026, 7, 20)),
            ),
            patch(
                "app.services.trading.agent_plan_ops.list_plan_views",
                AsyncMock(return_value=[]),
            ),
            patch(
                "app.services.trading.agent_plan_service.load_plan_content_for_date",
                AsyncMock(return_value=None),
            ),
        ):
            resp = http.get("/api/v1/admin/trading-agent/short-line/plans")

        assert resp.status_code == 200
        assert resp.json()["executingPlanDate"] == "2026-07-16"

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


def _observation_page() -> TradingAgentObservationPage:
    return TradingAgentObservationPage(
        trade_date=date(2026, 9, 29),
        total=1,
        page=1,
        page_size=20,
        items=[
            TradingAgentObservationItem(
                id=1,
                tick_time=datetime(2026, 9, 29, 1, 30, tzinfo=timezone.utc),
                trade_date=date(2026, 9, 29),
                agent_key="short-line",
                plan_id=11,
                stock_code="600000",
                stock_name="浦发银行",
                plan_type="buy",
                price=10.0,
                change_pct=1.01,
                l0_verdict="triggered",
                trigger_reason="buy_zone",
                decision=TradingAgentObservationDecision(
                    served_model="openjev-0.1",
                    choice="立即执行",
                    confidence=0.52,
                    noul=True,
                    score=3.0,
                    window=None,
                ),
                action="suppress",
                suppression_reason="below_threshold",
                is_shadow=True,
            )
        ],
        summary=TradingAgentObservationSummary(
            total_ticks=7,
            significant_ticks=1,
            l0_verdict_counts={"triggered": 1, "no_action": 6},
            action_counts={"suppress": 1},
            suppression_counts={"below_threshold": 1},
        ),
    )


@pytest.mark.unit
class TestTradingAgentObservations:
    def test_returns_camel_case_wire_with_default_filters(self, admin_client) -> None:
        http, _ = admin_client

        with patch(
            "app.services.trading.agent_exec_observation_service.list_agent_observations",
            AsyncMock(return_value=_observation_page()),
        ) as list_mock:
            resp = http.get("/api/v1/admin/trading-agent/short-line/observations")

        assert resp.status_code == 200
        list_mock.assert_awaited_once_with(
            admin_client[1],
            "short-line",
            trade_date=None,
            significant_only=True,
            page=1,
            page_size=20,
        )
        body = resp.json()
        item = body["items"][0]
        assert item["tickTime"].startswith("2026-09-29")
        assert item["l0Verdict"] == "triggered"
        assert item["triggerReason"] == "buy_zone"
        assert item["action"] == "suppress"
        assert item["suppressionReason"] == "below_threshold"
        assert item["isShadow"] is True
        assert item["decision"]["servedModel"] == "openjev-0.1"
        assert item["decision"]["confidence"] == pytest.approx(0.52)
        summary = body["summary"]
        assert summary["totalTicks"] == 7
        assert summary["significantTicks"] == 1
        assert summary["l0VerdictCounts"]["no_action"] == 6

    def test_query_params_pass_through(self, admin_client) -> None:
        http, _ = admin_client

        with patch(
            "app.services.trading.agent_exec_observation_service.list_agent_observations",
            AsyncMock(return_value=_observation_page()),
        ) as list_mock:
            resp = http.get(
                "/api/v1/admin/trading-agent/short-line/observations",
                params={
                    "trade_date": "2026-09-25",
                    "significant": "false",
                    "page": 2,
                    "page_size": 50,
                },
            )

        assert resp.status_code == 200
        list_mock.assert_awaited_once_with(
            admin_client[1],
            "short-line",
            trade_date=date(2026, 9, 25),
            significant_only=False,
            page=2,
            page_size=50,
        )

    def test_404_when_agent_unknown(self, admin_client) -> None:
        http, _ = admin_client

        with patch(
            "app.services.trading.agent_exec_observation_service.list_agent_observations",
            AsyncMock(side_effect=NotFoundError("交易 Agent ghost 不存在")),
        ):
            resp = http.get("/api/v1/admin/trading-agent/ghost/observations")

        assert resp.status_code == 404

    def test_422_on_out_of_range_pagination(self, admin_client) -> None:
        http, _ = admin_client

        with patch(
            "app.services.trading.agent_exec_observation_service.list_agent_observations",
            AsyncMock(return_value=_observation_page()),
        ) as list_mock:
            resp = http.get(
                "/api/v1/admin/trading-agent/short-line/observations",
                params={"page": 0},
            )

        assert resp.status_code == 422
        list_mock.assert_not_awaited()


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
                "app.services.trading.agent_plan_service.list_stand_aside_dates",
                AsyncMock(return_value=[date(2026, 7, 15)]),
            ) as stand_aside_mock,
            patch(
                "app.services.trading.agent_review_service.list_review_dates",
                AsyncMock(side_effect=lambda _s, _k, *, period: [date(2026, 7, period == "day" and 17 or 10)]),
            ) as review_dates_mock,
        ):
            resp = http.get("/api/v1/admin/trading-agent/short-line/dates")

        assert resp.status_code == 200
        body = resp.json()
        # 空仓观望日（无计划行）并入日历打点
        assert body["planDates"] == ["2026-07-15", "2026-07-16", "2026-07-17"]
        assert sorted(body["reviewDates"]) == ["day", "month", "week"]
        assert body["reviewDates"]["day"] == ["2026-07-17"]
        assert body["reviewDates"]["week"] == ["2026-07-10"]
        plan_dates_mock.assert_awaited_once()
        stand_aside_mock.assert_awaited_once()
        assert review_dates_mock.await_count == 3

    def test_empty_when_no_records(self, admin_client) -> None:
        http, _ = admin_client

        with (
            patch(
                "app.services.trading.agent_plan_ops.list_plan_dates",
                AsyncMock(return_value=[]),
            ),
            patch(
                "app.services.trading.agent_plan_service.list_stand_aside_dates",
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

    def test_delete_returns_204(self, admin_client) -> None:
        http, session = admin_client

        with patch(
            "app.api.v1.admin.trading_agent.agent_memory_service.delete_memory",
            AsyncMock(return_value=None),
        ) as delete_mock:
            resp = http.delete("/api/v1/admin/trading-agent/short-line/memories/3")

        assert resp.status_code == 204
        delete_mock.assert_awaited_once_with(session, "short-line", memory_id=3)

    def test_delete_404_when_missing(self, admin_client) -> None:
        from app.core.exceptions import NotFoundError

        http, _ = admin_client

        with patch(
            "app.api.v1.admin.trading_agent.agent_memory_service.delete_memory",
            AsyncMock(side_effect=NotFoundError("记忆 99 不存在")),
        ):
            resp = http.delete("/api/v1/admin/trading-agent/short-line/memories/99")

        assert resp.status_code == 404


@pytest.mark.unit
class TestTradingAgentCrud:
    """D29：Agent CRUD 端点（新建 201 / 删除 204 / 人设模板清单）。"""

    def test_prompt_templates_wire(self, admin_client) -> None:
        from app.schemas.paper_trade import TradingAgentPromptTemplate

        http, _ = admin_client
        with patch(
            "app.api.v1.admin.trading_agent.agent_registry.list_prompt_templates",
            MagicMock(
                return_value=[
                    TradingAgentPromptTemplate(
                        prompt_id="trading_agent_short_line", label="短线猎手"
                    )
                ]
            ),
        ) as templates_mock:
            resp = http.get("/api/v1/admin/trading-agent/prompt-templates")

        assert resp.status_code == 200
        body = resp.json()
        assert body[0]["promptId"] == "trading_agent_short_line"
        assert body[0]["label"] == "短线猎手"
        templates_mock.assert_called_once_with()

    def test_create_agent_returns_201_profile(self, admin_client) -> None:
        from app.schemas.paper_trade import TradingAgentProfileResponse

        http, session = admin_client
        profile = TradingAgentProfileResponse(
            agent_key="test-agent",
            name="测试 Agent",
            tagline="一句话",
            risk_max_position_pct=20.0,
            risk_max_total_pct=60.0,
            risk_max_daily_orders=10,
            intraday_exec_mode="off",
            status="active",
            sort_order=4,
            prompt_id="trading_agent_short_line",
            accent_color="#38bdf8",
        )
        with patch(
            "app.api.v1.admin.trading_agent.agent_registry.create_agent",
            AsyncMock(return_value=profile),
        ) as create_mock:
            resp = http.post(
                "/api/v1/admin/trading-agent/agents",
                json={
                    "agentKey": "test-agent",
                    "name": "测试 Agent",
                    "tagline": "一句话",
                    "promptId": "trading_agent_short_line",
                },
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["agentKey"] == "test-agent"
        assert body["status"] == "active"
        assert body["intradayExecMode"] == "off"
        create_mock.assert_awaited_once_with(session, data=create_mock.await_args.kwargs["data"])

    def test_create_agent_validation_error_surfaces_422(self, admin_client) -> None:
        from app.core.exceptions import UnprocessableEntityError

        http, _ = admin_client
        with patch(
            "app.api.v1.admin.trading_agent.agent_registry.create_agent",
            AsyncMock(side_effect=UnprocessableEntityError("人设模板 trading_agent_nope 不存在")),
        ):
            resp = http.post(
                "/api/v1/admin/trading-agent/agents",
                json={
                    "agentKey": "test-agent",
                    "name": "测试",
                    "tagline": "一句话",
                    "promptId": "trading_agent_nope",
                },
            )
        assert resp.status_code == 422

    def test_delete_agent_returns_204(self, admin_client) -> None:
        http, session = admin_client
        with patch(
            "app.api.v1.admin.trading_agent.agent_registry.delete_agent",
            AsyncMock(return_value=2),
        ) as delete_mock:
            resp = http.delete("/api/v1/admin/trading-agent/m60")

        assert resp.status_code == 204
        delete_mock.assert_awaited_once_with(session, "m60")

    def test_delete_agent_404(self, admin_client) -> None:
        from app.core.exceptions import NotFoundError

        http, _ = admin_client
        with patch(
            "app.api.v1.admin.trading_agent.agent_registry.delete_agent",
            AsyncMock(side_effect=NotFoundError("交易 Agent ghost 不存在")),
        ):
            resp = http.delete("/api/v1/admin/trading-agent/ghost")
        assert resp.status_code == 404


@pytest.mark.unit
class TestGetTradingAgentStatus:
    """D29 能力/状态端点：一屏回答 agent 靠什么工作。"""

    def _capability(self) -> AgentCapabilityResponse:
        from app.schemas.paper_trade import (
            AgentAutomationTask,
            AgentMemoryCounts,
            TradingAgentProfileResponse,
        )

        profile = TradingAgentProfileResponse(
            agent_key="short-line",
            name="短线猎手",
            tagline="日内强势股猎手",
            risk_max_position_pct=20.0,
            risk_max_total_pct=80.0,
            risk_max_daily_orders=10,
            intraday_exec_mode="shadow",
            status="active",
            sort_order=1,
            prompt_id="trading_agent_short_line",
            accent_color="#3b82f6",
        )
        return AgentCapabilityResponse(
            profile=profile,
            llm_name=None,
            methodology_source_name="趋势交易理论",
            skill_id="trading-short-line",
            skill_label="短线猎手作业程序",
            skill_is_shared_default=False,
            memory_counts=AgentMemoryCounts(discipline=2, method=1, lesson=3, active_total=6),
            automation=[
                AgentAutomationTask(
                    key="agent_daily_plan_1900",
                    label="每日选股与交易计划",
                    cron="0 19 * * 1-5",
                    task_active=True,
                    cadence="daily",
                )
            ],
            recent_activity=[],
        )

    def test_returns_camel_case_capability_wire(self, admin_client) -> None:
        from app.schemas.paper_trade import AgentCapabilityResponse

        http, session = admin_client
        capability: AgentCapabilityResponse = self._capability()
        with patch(
            "app.api.v1.admin.trading_agent.agent_overview_service.get_agent_status",
            AsyncMock(return_value=capability),
        ) as status_mock:
            resp = http.get("/api/v1/admin/trading-agent/short-line/status")

        assert resp.status_code == 200
        body = resp.json()
        assert body["profile"]["agentKey"] == "short-line"
        assert body["methodologySourceName"] == "趋势交易理论"
        assert body["skillId"] == "trading-short-line"
        assert body["skillIsSharedDefault"] is False
        assert body["memoryCounts"]["activeTotal"] == 6
        assert body["automation"][0]["taskActive"] is True
        assert body["automation"][0]["cadence"] == "daily"
        status_mock.assert_awaited_once_with(session, "short-line")


@pytest.mark.unit
class TestTradingAgentPromptAndSkillFiles:
    """D30 可视化端点：会话人设 YAML 原文 + 作业技能包文件与方法论。"""

    def test_prompt_returns_yaml_content(self, admin_client) -> None:
        from app.schemas.paper_trade import TradingAgentPromptContent

        http, session = admin_client
        with (
            patch(
                "app.api.v1.admin.trading_agent.agent_registry.get_agent",
                AsyncMock(return_value=MagicMock(prompt_id="trading_agent_short_line")),
            ) as get_mock,
            patch(
                "app.api.v1.admin.trading_agent.agent_registry.get_prompt_content",
                MagicMock(
                    return_value=TradingAgentPromptContent(
                        prompt_id="trading_agent_short_line",
                        label="短线猎手",
                        content="system_prompt: 打板纪律",
                    )
                ),
            ) as content_mock,
        ):
            resp = http.get("/api/v1/admin/trading-agent/short-line/prompt")

        assert resp.status_code == 200
        body = resp.json()
        assert body["promptId"] == "trading_agent_short_line"
        assert body["label"] == "短线猎手"
        assert "system_prompt" in body["content"]
        get_mock.assert_awaited_once_with(session, "short-line")
        content_mock.assert_called_once_with("trading_agent_short_line")

    def test_prompt_unknown_template_surfaces_404(self, admin_client) -> None:
        from app.core.exceptions import NotFoundError

        http, _ = admin_client
        with (
            patch(
                "app.api.v1.admin.trading_agent.agent_registry.get_agent",
                AsyncMock(return_value=MagicMock(prompt_id="ghost")),
            ),
            patch(
                "app.api.v1.admin.trading_agent.agent_registry.get_prompt_content",
                MagicMock(side_effect=NotFoundError("人设模板 ghost 不存在")),
            ),
        ):
            resp = http.get("/api/v1/admin/trading-agent/short-line/prompt")

        assert resp.status_code == 404

    def test_skill_files_returns_camel_case_wire(self, admin_client) -> None:
        from app.schemas.paper_trade import AgentSkillFilesResponse
        from app.schemas.skill import SkillFile

        http, session = admin_client
        payload = AgentSkillFilesResponse(
            skill_id="trading-short-line",
            skill_label="短线猎手作业程序",
            skill_is_shared_default=False,
            files=[SkillFile(path="SKILL.md", size=5, content="# 作业程序")],
            methodology=None,
        )
        with patch(
            "app.api.v1.admin.trading_agent.agent_overview_service.get_agent_skill_files",
            AsyncMock(return_value=payload),
        ) as files_mock:
            resp = http.get("/api/v1/admin/trading-agent/short-line/skill/files")

        assert resp.status_code == 200
        body = resp.json()
        assert body["skillId"] == "trading-short-line"
        assert body["skillLabel"] == "短线猎手作业程序"
        assert body["skillIsSharedDefault"] is False
        assert body["files"][0]["path"] == "SKILL.md"
        assert body["methodology"] is None
        files_mock.assert_awaited_once_with(session, "short-line")

    def test_skill_files_with_methodology_wire(self, admin_client) -> None:
        from app.schemas.paper_trade import (
            AgentMethodologyView,
            AgentSkillFilesResponse,
        )

        http, _ = admin_client
        payload = AgentSkillFilesResponse(
            skill_id="trading-default",
            skill_label="trading-default",
            skill_is_shared_default=True,
            files=[],
            methodology=AgentMethodologyView(
                source_id=1,
                source_name="趋势交易理论",
                outline="- 第一章 体系",
                disciplines=[{"title": "不追高", "body": "偏离 3% 不追"}],
                points=[{"title": "回踩接回", "point_type": "method", "body": "…"}],
            ),
        )
        with patch(
            "app.api.v1.admin.trading_agent.agent_overview_service.get_agent_skill_files",
            AsyncMock(return_value=payload),
        ):
            resp = http.get("/api/v1/admin/trading-agent/short-line/skill/files")

        assert resp.status_code == 200
        body = resp.json()
        assert body["skillIsSharedDefault"] is True
        assert body["methodology"]["sourceName"] == "趋势交易理论"
        assert body["methodology"]["disciplines"][0]["title"] == "不追高"
        assert body["methodology"]["points"][0]["pointType"] == "method"


@pytest.mark.unit
class TestCreateTradingAgentMemory:
    """手动沉淀记忆 POST（批次 9）：camelCase wire / 404 / 422。"""

    def _row(self) -> AgentMemory:
        return AgentMemory(
            id=9,
            agent_key="short-line",
            mem_type="lesson",
            title="不追高",
            body="偏离买点 3% 以上不追",
            source="manual",
            status="active",
            source_result_id=None,
            created_at=datetime(2026, 9, 27, tzinfo=timezone.utc),
            updated_at=datetime(2026, 9, 27, tzinfo=timezone.utc),
        )

    def test_returns_201_camel_case(self, admin_client) -> None:
        http, _ = admin_client
        with patch(
            "app.api.v1.admin.trading_agent.agent_memory_service.create_memory",
            AsyncMock(return_value=self._row()),
        ):
            resp = http.post(
                "/api/v1/admin/trading-agent/short-line/memories",
                json={"title": "不追高", "body": "偏离买点 3% 以上不追", "memType": "lesson"},
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["id"] == 9
        assert body["source"] == "manual"
        assert body["memType"] == "lesson"
        assert body["sourceResultId"] is None

    def test_404_when_agent_unknown(self, admin_client) -> None:
        http, _ = admin_client
        with patch(
            "app.api.v1.admin.trading_agent.agent_memory_service.create_memory",
            AsyncMock(side_effect=NotFoundError("交易 Agent nope 不存在")),
        ):
            resp = http.post(
                "/api/v1/admin/trading-agent/nope/memories",
                json={"title": "t", "body": "b", "memType": "method"},
            )

        assert resp.status_code == 404

    def test_422_on_unknown_mem_type(self, admin_client) -> None:
        http, _ = admin_client
        resp = http.post(
            "/api/v1/admin/trading-agent/short-line/memories",
            json={"title": "t", "body": "b", "memType": "habit"},
        )

        assert resp.status_code == 422
