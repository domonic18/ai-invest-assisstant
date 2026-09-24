"""知识库设置端点契约测试（GET/PUT /admin/kb/settings）。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_admin_user, get_db
from app.main import app


@pytest.fixture
def admin_client(client) -> tuple[TestClient, AsyncMock]:
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


def _settings_view_mock() -> MagicMock:
    # pydantic from_attributes 按 camel 别名优先读取，Mock 需两种拼写都置值
    view = MagicMock()
    pairs: dict[str, object] = {
        "hotwords": [],
        "segment_max_seconds": 30,
        "asr_concurrency": 2,
        "top_k": 8,
        "unit_prices": {},
        "embedding_config_id": None,
        "clean_model_id": None,
        "extract_model_id": None,
        "vision_model_id": None,
        "authorized_user_ids": [],
        "updated_at": None,
    }
    for snake, value in pairs.items():
        head, *rest = snake.split("_")
        camel = head + "".join(part.capitalize() for part in rest)
        setattr(view, snake, value)
        setattr(view, camel, value)
    return view


def test_get_settings_returns_camel_view(admin_client: tuple) -> None:
    http, session = admin_client
    with patch(
        "app.api.v1.admin.kb_settings.get_settings_view",
        new=AsyncMock(return_value=_settings_view_mock()),
    ):
        resp = http.get("/api/v1/admin/kb/settings")

    assert resp.status_code == 200
    body = resp.json()
    assert body["topK"] == 8
    assert body["segmentMaxSeconds"] == 30
    assert "segment_max_seconds" not in body


def test_put_settings_passes_admin_id(admin_client: tuple) -> None:
    http, session = admin_client
    view = _settings_view_mock()
    view.top_k = 12
    view.topK = 12
    with patch(
        "app.api.v1.admin.kb_settings.update_settings",
        new=AsyncMock(return_value=view),
    ) as p_update:
        resp = http.put(
            "/api/v1/admin/kb/settings",
            json={"topK": 12, "embeddingConfigId": 3},
        )

    assert resp.status_code == 200
    assert resp.json()["topK"] == 12
    kwargs = p_update.call_args.kwargs
    assert kwargs["admin_id"] == 1
    submitted = kwargs["data"]
    assert submitted.top_k == 12
    assert submitted.embedding_config_id == 3


def test_put_settings_requires_admin(client) -> None:
    app.dependency_overrides.clear()
    resp = client.get("/api/v1/admin/kb/settings")
    assert resp.status_code in (401, 403)
