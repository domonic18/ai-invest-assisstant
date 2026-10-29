"""管理后台 MCP API Key 端点契约测试（camelCase wire / 201 一次性明文 / 422 / 404）。"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import NotFoundError
from app.dependencies import get_current_admin_user, get_db
from app.main import app
from app.schemas.api_key import ApiKeyIssuedResponse, ApiKeyResponse

pytestmark = pytest.mark.unit


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


def _response(**overrides: object) -> ApiKeyResponse:
    base: dict[str, object] = {
        "id": 3,
        "user_id": 7,
        "username": "alice",
        "name": "飞书助手",
        "key_prefix": "inv_0a1b2c3d",
        "scopes": ["market:read", "kb:read"],
        "expires_at": None,
        "revoked_at": None,
        "last_used_at": None,
        "created_at": datetime(2026, 10, 29, tzinfo=timezone.utc),
    }
    base.update(overrides)
    return ApiKeyResponse(**base)


def test_list_api_keys_wire_is_camel_case(admin_client):
    client, _ = admin_client
    with patch(
        "app.api.v1.admin.api_keys.ApiKeyService.list_keys",
        AsyncMock(return_value=[_response()]),
    ) as mocked:
        response = client.get("/api/v1/admin/api-keys/?user_id=7")

    assert response.status_code == 200
    mocked.assert_awaited_once_with(7)
    body = response.json()
    assert body[0]["userId"] == 7
    assert body[0]["keyPrefix"] == "inv_0a1b2c3d"
    assert body[0]["createdAt"].startswith("2026-10-29")
    assert "keyHash" not in body[0]


def test_create_api_key_returns_plaintext_once(admin_client):
    client, _ = admin_client
    issued = ApiKeyIssuedResponse(
        **_response().model_dump(), token="inv_0a1b2c3d_secret"
    )
    with patch(
        "app.api.v1.admin.api_keys.ApiKeyService.create_key",
        AsyncMock(return_value=issued),
    ) as mocked:
        response = client.post(
            "/api/v1/admin/api-keys/",
            json={
                "userId": 7,
                "name": "飞书助手",
                "scopes": ["market:read", "kb:read"],
            },
        )

    assert response.status_code == 201
    kwargs = mocked.await_args.kwargs
    assert kwargs["user_id"] == 7
    assert kwargs["scopes"] == ["market:read", "kb:read"]
    assert response.json()["token"] == "inv_0a1b2c3d_secret"


@pytest.mark.parametrize(
    "payload",
    [
        {"userId": 7, "name": "x", "scopes": ["not:a:scope"]},
        {"userId": 7, "name": "x", "scopes": []},
        {"userId": 0, "name": "x", "scopes": ["kb:read"]},
        {"userId": 7, "name": "", "scopes": ["kb:read"]},
    ],
)
def test_create_api_key_rejects_invalid_payload(admin_client, payload):
    client, _ = admin_client
    with patch(
        "app.api.v1.admin.api_keys.ApiKeyService.create_key", AsyncMock()
    ) as mocked:
        response = client.post("/api/v1/admin/api-keys/", json=payload)

    assert response.status_code == 422
    mocked.assert_not_awaited()


def test_revoke_api_key_returns_204(admin_client):
    client, _ = admin_client
    with patch(
        "app.api.v1.admin.api_keys.ApiKeyService.revoke_key", AsyncMock()
    ) as mocked:
        response = client.delete("/api/v1/admin/api-keys/3")

    assert response.status_code == 204
    mocked.assert_awaited_once_with(3)


def test_revoke_api_key_missing_returns_404(admin_client):
    client, _ = admin_client
    with patch(
        "app.api.v1.admin.api_keys.ApiKeyService.revoke_key",
        AsyncMock(side_effect=NotFoundError("API Key 404 不存在")),
    ):
        response = client.delete("/api/v1/admin/api-keys/404")

    assert response.status_code == 404
    assert response.json()["detail"] == "API Key 404 不存在"
