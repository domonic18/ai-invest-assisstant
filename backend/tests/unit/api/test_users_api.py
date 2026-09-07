"""用户资料端点契约测试（邮箱更新 / 修改密码 / camelCase wire）。"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import BadRequestError, ConflictError
from app.dependencies import get_current_user
from app.main import app
from app.schemas.user import UserResponse

_NOW = datetime(2026, 9, 7, tzinfo=timezone.utc)


@pytest.fixture
def user():
    return type(
        "User",
        (object,),
        {"id": 1, "username": "user", "role": "user", "is_active": True},
    )()


@pytest.fixture
def auth_client(client, user):
    app.dependency_overrides[get_current_user] = lambda: user
    yield client
    app.dependency_overrides.clear()


def _user_response() -> UserResponse:
    return UserResponse(
        id=1,
        username="user",
        email="new@example.com",
        role="user",
        is_active=True,
        last_login_at=None,
        created_at=_NOW,
    )


@pytest.mark.unit
class TestUsersMeApi:
    def test_update_me_email(self, auth_client, user) -> None:
        with patch("app.api.v1.users.UserService") as mock_service:
            mock_service.return_value.update_email = AsyncMock(return_value=_user_response())
            response = auth_client.put("/api/v1/users/me", json={"email": "new@example.com"})

        assert response.status_code == 200
        assert response.json()["email"] == "new@example.com"
        mock_service.return_value.update_email.assert_awaited_once_with(
            user, "new@example.com"
        )

    def test_update_me_email_conflict_returns_409(self, auth_client) -> None:
        with patch("app.api.v1.users.UserService") as mock_service:
            mock_service.return_value.update_email = AsyncMock(
                side_effect=ConflictError("该邮箱已被使用")
            )
            response = auth_client.put("/api/v1/users/me", json={"email": "taken@example.com"})

        assert response.status_code == 409

    def test_update_me_invalid_email_returns_422(self, auth_client) -> None:
        response = auth_client.put("/api/v1/users/me", json={"email": "not-an-email"})

        assert response.status_code == 422

    def test_change_password_returns_204(self, auth_client, user) -> None:
        with patch("app.api.v1.users.UserService") as mock_service:
            mock_service.return_value.change_password = AsyncMock()
            response = auth_client.post(
                "/api/v1/users/me/password",
                json={"currentPassword": "old123", "newPassword": "new123456"},
            )

        assert response.status_code == 204
        mock_service.return_value.change_password.assert_awaited_once_with(
            user, "old123", "new123456"
        )

    def test_change_password_wrong_current_returns_400(self, auth_client) -> None:
        with patch("app.api.v1.users.UserService") as mock_service:
            mock_service.return_value.change_password = AsyncMock(
                side_effect=BadRequestError("当前密码不正确")
            )
            response = auth_client.post(
                "/api/v1/users/me/password",
                json={"currentPassword": "wrong", "newPassword": "new123456"},
            )

        assert response.status_code == 400

    def test_change_password_too_short_returns_422(self, auth_client) -> None:
        response = auth_client.post(
            "/api/v1/users/me/password",
            json={"currentPassword": "old123", "newPassword": "123"},
        )

        assert response.status_code == 422
