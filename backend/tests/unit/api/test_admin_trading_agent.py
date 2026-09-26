"""交易 Agent admin 端点契约测试（复盘查询：camelCase wire / 404 / 422）。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_admin_user, get_db
from app.main import app


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
