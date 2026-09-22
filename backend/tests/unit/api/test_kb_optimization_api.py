"""技能优化建议端点契约测试（/admin/kb/optimization-suggestions）。"""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_admin_user, get_db
from app.main import app

_TS = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)

pytestmark = pytest.mark.unit

_SUGGESTION_ITEM: dict[str, Any] = {
    "targetFile": "prompt.yaml",
    "section": "分析框架",
    "originalText": "旧文",
    "suggestedText": "新文",
    "reason": "缺少量价确认",
    "citations": ["《价值投资课》 第3集 05:30-06:10"],
}


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


def _set_both(mock: MagicMock, snake: str, value: object) -> None:
    head, *rest = snake.split("_")
    camel = head + "".join(part.capitalize() for part in rest)
    setattr(mock, snake, value)
    setattr(mock, camel, value)


def _row_mock(**overrides: object) -> MagicMock:
    fields: dict[str, object] = {
        "id": 7,
        "skill_id": "market-daily-review",
        "skill_label": "大盘复盘",
        "skill_kind": "builtin",
        "skill_version": 3,
        "source_id": 1,
        "source_name": "价值投资课",
        "status": "pending_review",
        "skill_definition": "===== SKILL.md =====\nx",
        "suggestions": [
            {
                "target_file": "prompt.yaml",
                "section": "分析框架",
                "original_text": "旧文",
                "suggested_text": "新文",
                "reason": "缺少量价确认",
                "citations": ["《价值投资课》 第3集 05:30-06:10"],
            }
        ],
        "summary": "整体加强引用规范",
        "model_name": "kimi/k2",
        "error": None,
        "reviewed_by": None,
        "reviewed_at": None,
        "review_note": None,
        "apply_result": None,
        "created_by": 1,
        "created_at": _TS,
        "updated_at": _TS,
    }
    fields.update(overrides)
    row = MagicMock()
    for snake, value in fields.items():
        _set_both(row, snake, value)
    return row


def test_list_suggestions_passes_filters(admin_client: tuple) -> None:
    http, _ = admin_client
    with patch(
        "app.services.kb.optimization_service.list_suggestions",
        new=AsyncMock(return_value=([_row_mock()], 3)),
    ) as p_list:
        resp = http.get(
            "/api/v1/admin/kb/optimization-suggestions",
            params={"status": "pending_review", "page": 2, "page_size": 10},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3 and body["page"] == 2 and body["pageSize"] == 10
    assert body["items"][0]["skillId"] == "market-daily-review"
    assert body["items"][0]["suggestions"][0] == _SUGGESTION_ITEM
    assert p_list.call_args.kwargs["status"] == "pending_review"
    assert p_list.call_args.kwargs["page"] == 2


def test_create_suggestion_returns_201(admin_client: tuple) -> None:
    http, _ = admin_client
    with patch(
        "app.services.kb.optimization_service.create_suggestion",
        new=AsyncMock(return_value=_row_mock(status="queued")),
    ) as p_create:
        resp = http.post(
            "/api/v1/admin/kb/optimization-suggestions",
            json={"skillId": "market-daily-review", "sourceId": 1},
        )
    assert resp.status_code == 201
    assert resp.json()["status"] == "queued"
    # camelCase 入参映射到 snake_case 服务参数；actor 取当前管理员
    assert p_create.call_args.kwargs["skill_id"] == "market-daily-review"
    assert p_create.call_args.kwargs["source_id"] == 1
    assert p_create.call_args.kwargs["actor_id"] == 1


def test_create_suggestion_validates_payload(admin_client: tuple) -> None:
    http, _ = admin_client
    resp = http.post(
        "/api/v1/admin/kb/optimization-suggestions", json={"skillId": "x"}
    )
    assert resp.status_code == 422


def test_get_suggestion_detail(admin_client: tuple) -> None:
    http, _ = admin_client
    with patch(
        "app.services.kb.optimization_service.get_suggestion",
        new=AsyncMock(return_value=_row_mock()),
    ) as p_get:
        resp = http.get("/api/v1/admin/kb/optimization-suggestions/7")
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending_review"
    assert resp.json()["modelName"] == "kimi/k2"
    p_get.assert_awaited_once()


def test_review_suggestion_routes(admin_client: tuple) -> None:
    http, _ = admin_client
    with patch(
        "app.services.kb.optimization_service.review_suggestion",
        new=AsyncMock(return_value=_row_mock(status="applied", review_note="ok")),
    ) as p_review:
        resp = http.post(
            "/api/v1/admin/kb/optimization-suggestions/7/review",
            json={
                "action": "apply",
                "revisions": [{"index": 0, "suggestedText": "修订文本"}],
            },
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "applied"
    assert p_review.call_args.kwargs["action"] == "apply"
    assert p_review.call_args.kwargs["revisions"] == {0: "修订文本"}
    assert p_review.call_args.kwargs["actor_id"] == 1


def test_review_suggestion_validates_action(admin_client: tuple) -> None:
    http, _ = admin_client
    resp = http.post(
        "/api/v1/admin/kb/optimization-suggestions/7/review",
        json={"action": "delete"},
    )
    assert resp.status_code == 422
