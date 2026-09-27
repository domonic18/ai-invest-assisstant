"""Agent 会话管理 admin 端点契约测试（D35：camelCase wire / 筛选映射 / 404）。

query 参数走后端 FastAPI 签名 snake_case（不随 body camelCase）；响应体经
CamelModel 输出 camelCase，summary/payload 为 JSONB 字典值原样透传（内键
snake_case 不转换）。
"""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_admin_user, get_db
from app.main import app
from app.models.agent_run import AgentRun, AgentRunStep


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


def _run_row(**overrides) -> AgentRun:
    fields = dict(
        id=42,
        agent_key="short-line",
        kind="plan",
        period="day",
        trigger_type="scheduled",
        trade_date=date(2026, 7, 15),
        status="success",
        started_at=datetime(2026, 7, 15, 11, 30, tzinfo=timezone.utc),
        finished_at=datetime(2026, 7, 15, 11, 32, tzinfo=timezone.utc),
        duration_ms=120000,
        error_msg=None,
        summary={"cache_hit": False, "selections": 1},
        collector_log_id=9,
    )
    fields.update(overrides)
    return AgentRun(**fields)


def _step_row(**overrides) -> AgentRunStep:
    fields = dict(
        run_id=42,
        seq=1,
        step_key="llm",
        title="LLM 结构化生成",
        status="success",
        started_at=datetime(2026, 7, 15, 11, 30, 5, tzinfo=timezone.utc),
        duration_ms=90000,
        payload={"prompt": "全文", "meta": {"model_name": "kimi"}},
    )
    fields.update(overrides)
    return AgentRunStep(**fields)


def _repo_patch(total: int, rows: list[AgentRun]) -> MagicMock:
    repo_cls = MagicMock()
    repo_cls.return_value.list_runs = AsyncMock(return_value=(total, rows))
    return repo_cls


@pytest.mark.unit
class TestListAgentRuns:
    def test_returns_camel_case_wire(self, admin_client) -> None:
        http, _ = admin_client
        repo_cls = _repo_patch(1, [_run_row()])
        with patch("app.api.v1.admin.agent_runs.AgentRunRepository", repo_cls):
            resp = http.get("/api/v1/admin/agent-runs")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["page"] == 1
        row = body["items"][0]
        assert row["agentKey"] == "short-line"
        assert row["triggerType"] == "scheduled"
        assert row["tradeDate"] == "2026-07-15"
        assert row["durationMs"] == 120000
        assert row["collectorLogId"] == 9
        # JSONB 字典值不走 camelCase 转换（前端按 snake_case 读取）
        assert row["summary"]["cache_hit"] is False

    def test_passes_snake_case_filters_to_repository(self, admin_client) -> None:
        """筛选/分页参数按 FastAPI 签名 snake_case 透传仓储。"""
        http, _ = admin_client
        repo_cls = _repo_patch(0, [])
        with patch("app.api.v1.admin.agent_runs.AgentRunRepository", repo_cls):
            resp = http.get(
                "/api/v1/admin/agent-runs",
                params={
                    "page": 2,
                    "page_size": 5,
                    "agent_key": "short-line",
                    "kind": "review",
                    "period": "week",
                    "status": "failed",
                    "trigger_type": "manual",
                    "trade_date_start": "2026-07-01",
                    "trade_date_end": "2026-07-15",
                },
            )

        assert resp.status_code == 200
        repo = repo_cls.return_value
        assert repo.list_runs.await_args.args == (2, 5)
        kwargs = repo.list_runs.await_args.kwargs
        assert kwargs["agent_key"] == "short-line"
        assert kwargs["kind"] == "review"
        assert kwargs["period"] == "week"
        assert kwargs["status"] == "failed"
        assert kwargs["trigger_type"] == "manual"
        assert kwargs["trade_date_start"] == date(2026, 7, 1)
        assert kwargs["trade_date_end"] == date(2026, 7, 15)


@pytest.mark.unit
class TestGetAgentRun:
    def test_detail_returns_steps_with_camel_wire(self, admin_client) -> None:
        http, _ = admin_client
        repo_cls = MagicMock()
        repo_cls.return_value.get_with_steps = AsyncMock(
            return_value=(_run_row(), [_step_row()])
        )
        with patch("app.api.v1.admin.agent_runs.AgentRunRepository", repo_cls):
            resp = http.get("/api/v1/admin/agent-runs/42")

        assert resp.status_code == 200
        body = resp.json()
        assert body["agentKey"] == "short-line"
        repo = repo_cls.return_value
        repo.get_with_steps.assert_awaited_once_with(42)
        step = body["steps"][0]
        assert step["stepKey"] == "llm"
        assert step["seq"] == 1
        assert step["durationMs"] == 90000
        # payload 内键由 step_key 决定，原样透传（snake_case 不转换）
        assert step["payload"]["meta"]["model_name"] == "kimi"
        assert step["payload"]["prompt"] == "全文"

    def test_404_when_run_missing(self, admin_client) -> None:
        http, _ = admin_client
        repo_cls = MagicMock()
        repo_cls.return_value.get_with_steps = AsyncMock(return_value=None)
        with patch("app.api.v1.admin.agent_runs.AgentRunRepository", repo_cls):
            resp = http.get("/api/v1/admin/agent-runs/999")

        assert resp.status_code == 404
