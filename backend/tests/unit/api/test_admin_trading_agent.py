"""交易 Agent admin 端点契约测试（复盘/交易计划查询：camelCase wire / 404 / 422）。"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_admin_user, get_db
from app.main import app
from app.models.agent_trading import AgentTradePlan


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
        row.structured_output = _content()

        with patch(
            "app.repositories.review.ai_analysis_repository.load_latest_success",
            AsyncMock(return_value=row),
        ):
            resp = http.get("/api/v1/admin/trading-agent/review", params={"period": "day"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["tradeDate"] == "2026-07-17"
        assert body["trades"][0]["clOrdId"] == "A"
        assert body["trades"][0]["selectionVerdict"] == "correct"
        assert body["experiences"][0]["memType"] == "discipline"

    def test_404_when_not_generated(self, admin_client) -> None:
        http, _ = admin_client

        with patch(
            "app.repositories.review.ai_analysis_repository.load_latest_success",
            AsyncMock(return_value=None),
        ):
            resp = http.get("/api/v1/admin/trading-agent/review", params={"period": "day"})

        assert resp.status_code == 404
        assert "尚未生成" in resp.json()["detail"]

    def test_422_on_unknown_period(self, admin_client) -> None:
        http, _ = admin_client

        resp = http.get(
            "/api/v1/admin/trading-agent/review", params={"period": "year"}
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
                "app.services.trading.agent_plan_ops.list_plans",
                AsyncMock(return_value=[_plan_row()]),
            ),
        ):
            resp = http.get("/api/v1/admin/trading-agent/plans")

        assert resp.status_code == 200
        body = resp.json()
        assert body[0]["planDate"] == "2026-07-17"
        assert body[0]["planType"] == "buy"
        assert body[0]["buyZoneLow"] == pytest.approx(9.9)
        assert body[0]["buyZoneHigh"] == pytest.approx(10.2)
        assert body[0]["stopLoss"] == pytest.approx(9.5)
        assert body[0]["positionPct"] == pytest.approx(10.0)
        assert body[0]["triggeredClOrdId"] is None

    def test_list_accepts_trade_date_query(self, admin_client) -> None:
        http, _ = admin_client

        with (
            patch(
                "app.services.market.trade_calendar_service.resolve_latest_trade_date",
                AsyncMock(),
            ) as resolve_mock,
            patch(
                "app.services.trading.agent_plan_ops.list_plans",
                AsyncMock(return_value=[]),
            ) as list_mock,
        ):
            resp = http.get(
                "/api/v1/admin/trading-agent/plans", params={"trade_date": "2026-07-16"}
            )

        assert resp.status_code == 200
        resolve_mock.assert_not_awaited()
        assert list_mock.await_args.kwargs["plan_date"] == date(2026, 7, 16)

    def test_cancel_returns_updated_plan(self, admin_client) -> None:
        http, _ = admin_client

        with patch(
            "app.services.trading.agent_plan_ops.cancel_plan",
            AsyncMock(return_value=_plan_row(status="cancelled")),
        ) as cancel_mock:
            resp = http.post("/api/v1/admin/trading-agent/plans/11/cancel")

        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"
        cancel_mock.assert_awaited_once_with(admin_client[1], plan_id=11)
