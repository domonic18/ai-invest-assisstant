"""个人设置 MCP API Key 自助端点契约测试（仅本人 Key / scope 服务端固定）。"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.constants import API_KEY_SELF_SERVICE_SCOPES
from app.core.exceptions import NotFoundError
from app.dependencies import get_current_user, get_db
from app.main import app
from app.schemas.api_key import ApiKeyIssuedResponse, ApiKeyResponse

pytestmark = pytest.mark.unit

_URL = "/api/v1/users/me/api-keys/"


@pytest.fixture
def me_client(client) -> tuple[TestClient, AsyncMock]:
    mock_session = AsyncMock()
    mock_user = MagicMock()
    mock_user.id = 7
    mock_user.role = "user"

    async def _override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield client, mock_session
    app.dependency_overrides.clear()


def _response(**overrides: object) -> ApiKeyResponse:
    base: dict[str, object] = {
        "id": 3,
        "user_id": 7,
        "username": "alice",
        "name": "飞书助手",
        "key_prefix": "inv_0a1b2c3d",
        "scopes": list(API_KEY_SELF_SERVICE_SCOPES),
        "expires_at": None,
        "revoked_at": None,
        "last_used_at": None,
        "created_at": datetime(2026, 10, 29, tzinfo=timezone.utc),
    }
    base.update(overrides)
    return ApiKeyResponse(**base)


def test_list_my_api_keys_uses_current_user(me_client):
    client, _ = me_client
    with patch(
        "app.api.v1.user_api_keys.ApiKeyService.list_keys",
        AsyncMock(return_value=[_response()]),
    ) as mocked:
        response = client.get(_URL)

    assert response.status_code == 200
    mocked.assert_awaited_once_with(7)
    body = response.json()
    assert body[0]["keyPrefix"] == "inv_0a1b2c3d"
    assert body[0]["userId"] == 7
    assert "keyHash" not in body[0]


def test_create_my_api_key_forces_current_user_and_default_scopes(me_client):
    client, _ = me_client
    issued = ApiKeyIssuedResponse(
        **_response().model_dump(), token="inv_0a1b2c3d_secret"
    )
    with patch(
        "app.api.v1.user_api_keys.ApiKeyService.create_key",
        AsyncMock(return_value=issued),
    ) as mocked:
        response = client.post(
            _URL,
            json={"name": "飞书助手", "userId": 99, "scopes": ["watchlist:write"]},
        )

    assert response.status_code == 201
    kwargs = mocked.await_args.kwargs
    assert kwargs["user_id"] == 7
    assert kwargs["scopes"] == list(API_KEY_SELF_SERVICE_SCOPES)
    assert response.json()["token"] == "inv_0a1b2c3d_secret"


@pytest.mark.parametrize("name", ["", "x" * 101])
def test_create_my_api_key_rejects_invalid_name(me_client, name):
    client, _ = me_client
    with patch(
        "app.api.v1.user_api_keys.ApiKeyService.create_key", AsyncMock()
    ) as mocked:
        response = client.post(_URL, json={"name": name})

    assert response.status_code == 422
    mocked.assert_not_awaited()


def test_revoke_my_api_key_scopes_to_current_user(me_client):
    client, _ = me_client
    with patch(
        "app.api.v1.user_api_keys.ApiKeyService.revoke_own_key", AsyncMock()
    ) as mocked:
        response = client.delete(f"{_URL}3")

    assert response.status_code == 204
    mocked.assert_awaited_once_with(3, 7)


def test_revoke_my_api_key_foreign_key_returns_404(me_client):
    client, _ = me_client
    with patch(
        "app.api.v1.user_api_keys.ApiKeyService.revoke_own_key",
        AsyncMock(side_effect=NotFoundError("API Key 3 不存在")),
    ):
        response = client.delete(f"{_URL}3")

    assert response.status_code == 404
    assert response.json()["detail"] == "API Key 3 不存在"


def test_requires_login(client):
    response = client.get(_URL)
    assert response.status_code == 401
