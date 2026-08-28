"""assistant 协议端点单测（TestClient + dependency override + mock agent）。"""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import HumanMessage, ToolMessage

from app.dependencies import get_current_user, get_db
from app.main import app
from app.models.assistant_session import AssistantSession


def _session_row(title: str | None = None) -> AssistantSession:
    now = datetime.now(timezone.utc)
    return AssistantSession(
        id=uuid.uuid4(), user_id=1, title=title, created_at=now, updated_at=now
    )


@pytest.fixture
def assistant_client():
    mock_session = AsyncMock()
    mock_user = MagicMock()
    mock_user.id = 1

    async def _override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield TestClient(app), mock_user
    app.dependency_overrides.clear()


@pytest.mark.unit
class TestThreadEndpoints:
    def test_create_thread_returns_thread_id(self, assistant_client) -> None:
        client, _ = assistant_client
        row = _session_row()
        with patch(
            "app.services.assistant.assistant_service.AssistantService.create_session",
            AsyncMock(return_value=row),
        ):
            response = client.post("/api/v1/assistant/threads", json={})
        assert response.status_code == 200
        body = response.json()
        assert body["thread_id"] == str(row.id)
        assert body["metadata"]["user_id"] == 1

    def test_list_sessions_shape(self, assistant_client) -> None:
        client, _ = assistant_client
        row = _session_row("平安银行")
        with patch(
            "app.services.assistant.assistant_service.AssistantService.list_sessions",
            AsyncMock(return_value=([row], 1)),
        ):
            response = client.get("/api/v1/assistant/sessions")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["sessions"][0]["title"] == "平安银行"

    def test_state_requires_owned_thread(self, assistant_client) -> None:
        client, _ = assistant_client
        with patch(
            "app.services.assistant.assistant_service.AssistantService.get_session",
            AsyncMock(return_value=None),
        ):
            response = client.get(
                f"/api/v1/assistant/threads/{uuid.uuid4()}/state"
            )
        assert response.status_code == 404

    def test_state_serializes_messages_and_interrupts(self, assistant_client) -> None:
        client, _ = assistant_client
        snapshot = MagicMock()
        snapshot.values = {"messages": [HumanMessage(content="hi", id="h1")]}
        snapshot.next = []
        snapshot.tasks = []
        snapshot.metadata = {}
        agent = MagicMock()
        agent.aget_state = AsyncMock(return_value=snapshot)
        with (
            patch(
                "app.services.assistant.assistant_service.AssistantService.get_session",
                AsyncMock(return_value=_session_row()),
            ),
            patch(
                "app.api.v1.assistant.runs.get_assistant_agent",
                AsyncMock(return_value=agent),
            ),
        ):
            response = client.get(
                f"/api/v1/assistant/threads/{uuid.uuid4()}/state"
            )
        assert response.status_code == 200
        body = response.json()
        assert body["values"]["messages"][0]["type"] == "human"
        assert body["values"]["messages"][0]["content"] == "hi"

    def test_delete_thread_404_when_not_owned(self, assistant_client) -> None:
        client, _ = assistant_client
        with patch(
            "app.services.assistant.assistant_service.AssistantService.delete_session",
            AsyncMock(return_value=False),
        ):
            response = client.delete(f"/api/v1/assistant/threads/{uuid.uuid4()}")
        assert response.status_code == 404


@pytest.mark.unit
class TestRunStream:
    def test_rejects_non_human_input_message(self, assistant_client) -> None:
        client, _ = assistant_client
        with patch(
            "app.services.assistant.assistant_service.AssistantService.get_session",
            AsyncMock(return_value=_session_row()),
        ):
            response = client.post(
                f"/api/v1/assistant/threads/{uuid.uuid4()}/runs/stream",
                json={"input": {"messages": [{"type": "ai", "content": "x"}]}},
            )
        assert response.status_code == 422

    def test_page_context_prefixes_user_message(self) -> None:
        from app.api.v1.assistant.page_context import _with_page_context

        result = _with_page_context(
            "这只股票最近走势如何？",
            {"page": "个股详情", "stock_code": "000001", "route": "/stock/000001"},
        )
        assert result.startswith('[页面上下文] {"page": "个股详情"')
        assert result.endswith("这只股票最近走势如何？")

    def test_page_context_absent_keeps_content(self) -> None:
        from app.api.v1.assistant.page_context import _with_page_context

        assert _with_page_context("你好", None) == "你好"
        assert _with_page_context("你好", {}) == "你好"

    def test_page_context_block_list_prepends_text_block(self) -> None:
        from app.api.v1.assistant.page_context import _with_page_context

        blocks = [{"type": "text", "text": "问题"}]
        result = _with_page_context(blocks, {"page": "资金流向"})
        assert isinstance(result, list)
        assert result[0]["type"] == "text"
        assert result[0]["text"].startswith("[页面上下文]")
        assert result[1] == blocks[0]

    def test_cancel_unknown_run_404(self, assistant_client) -> None:
        client, _ = assistant_client
        with patch(
            "app.services.assistant.assistant_service.AssistantService.get_session",
            AsyncMock(return_value=_session_row()),
        ):
            response = client.post(
                f"/api/v1/assistant/threads/{uuid.uuid4()}/runs/deadbeef/cancel"
            )
        assert response.status_code == 404

    def test_stream_emits_custom_event_from_tool_message(self, assistant_client) -> None:
        client, _ = assistant_client

        async def _fake_astream(*args, **kwargs):
            tool_msg = ToolMessage(
                content=json.dumps(
                    {
                        "industry": "半导体",
                        "version_id": 123,
                        "version_no": 5,
                        "status": "success",
                        "__event__": {
                            "type": "industry_chain.analysis_complete",
                            "industry": "半导体",
                            "version_id": 123,
                            "version_no": 5,
                        },
                    },
                    ensure_ascii=False,
                ),
                tool_call_id="call1",
                name="persist_chain_analysis",
                id="t1",
            )
            yield (), "messages", (tool_msg, {})

        agent = MagicMock()
        agent.astream = _fake_astream
        with (
            patch(
                "app.services.assistant.assistant_service.AssistantService.get_session",
                AsyncMock(return_value=_session_row()),
            ),
            patch(
                "app.api.v1.assistant.runs.get_assistant_agent",
                AsyncMock(return_value=agent),
            ),
            patch(
                "app.api.v1.assistant.runs.touch_session_standalone",
                AsyncMock(return_value=None),
            ),
        ):
            response = client.post(
                f"/api/v1/assistant/threads/{uuid.uuid4()}/runs/stream",
                json={"input": {"messages": [{"type": "human", "content": "分析半导体"}]}},
            )
        assert response.status_code == 200
        text = response.text
        assert 'event: messages' in text
        assert 'event: custom' in text
        assert 'industry_chain.analysis_complete' in text


@pytest.mark.unit
class TestSkillsEndpoint:
    def test_skills_empty_when_dir_missing(self, assistant_client) -> None:
        client, _ = assistant_client
        settings = MagicMock()
        settings.skills_dir = MagicMock()
        settings.skills_dir.exists.return_value = False
        with patch(
            "app.services.assistant.assistant_service.get_settings", return_value=settings
        ):
            response = client.get("/api/v1/assistant/skills")
        assert response.status_code == 200
        assert response.json() == []
