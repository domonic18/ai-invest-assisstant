"""assistant 协议端点单测（TestClient + dependency override + mock agent）。"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import HumanMessage

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
            "app.services.assistant_service.AssistantService.create_session",
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
            "app.services.assistant_service.AssistantService.list_sessions",
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
            "app.services.assistant_service.AssistantService.get_session",
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
                "app.services.assistant_service.AssistantService.get_session",
                AsyncMock(return_value=_session_row()),
            ),
            patch(
                "app.api.v1.assistant.get_assistant_agent",
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
            "app.services.assistant_service.AssistantService.delete_session",
            AsyncMock(return_value=False),
        ):
            response = client.delete(f"/api/v1/assistant/threads/{uuid.uuid4()}")
        assert response.status_code == 404


@pytest.mark.unit
class TestRunStream:
    def test_rejects_non_human_input_message(self, assistant_client) -> None:
        client, _ = assistant_client
        with patch(
            "app.services.assistant_service.AssistantService.get_session",
            AsyncMock(return_value=_session_row()),
        ):
            response = client.post(
                f"/api/v1/assistant/threads/{uuid.uuid4()}/runs/stream",
                json={"input": {"messages": [{"type": "ai", "content": "x"}]}},
            )
        assert response.status_code == 422

    def test_cancel_unknown_run_404(self, assistant_client) -> None:
        client, _ = assistant_client
        with patch(
            "app.services.assistant_service.AssistantService.get_session",
            AsyncMock(return_value=_session_row()),
        ):
            response = client.post(
                f"/api/v1/assistant/threads/{uuid.uuid4()}/runs/deadbeef/cancel"
            )
        assert response.status_code == 404


@pytest.mark.unit
class TestSkillsEndpoint:
    def test_skills_empty_when_dir_missing(self, assistant_client) -> None:
        client, _ = assistant_client
        settings = MagicMock()
        settings.skills_dir = MagicMock()
        settings.skills_dir.exists.return_value = False
        with patch(
            "app.api.v1.assistant.get_settings", return_value=settings
        ):
            response = client.get("/api/v1/assistant/skills")
        assert response.status_code == 200
        assert response.json() == []
