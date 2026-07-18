from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.unit
class TestAuthEndpoints:
    def test_register_success(self, client) -> None:
        mock_user = type(
            "User",
            (object,),
            {
                "id": 1,
                "username": "tester",
                "email": "test@example.com",
                "role": "user",
                "is_active": True,
                "last_login_at": None,
                "created_at": "2024-01-01T00:00:00",
            },
        )()

        with patch("app.api.v1.auth.UserService") as mock_user_service:
            instance = mock_user_service.return_value
            instance.get_user_by_username = AsyncMock(return_value=None)
            instance.get_user_by_email = AsyncMock(return_value=None)
            instance.create_user = AsyncMock(return_value=mock_user)
            response = client.post(
                "/api/v1/auth/register",
                json={
                    "username": "tester",
                    "email": "test@example.com",
                    "password": "secret123",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["user"]["username"] == "tester"
        assert "access_token" in data

    def test_login_invalid_credentials(self, client) -> None:
        with patch("app.api.v1.auth.UserService") as mock_user_service:
            instance = mock_user_service.return_value
            instance.authenticate_user = AsyncMock(return_value=None)
            response = client.post(
                "/api/v1/auth/login",
                data={"username": "tester", "password": "wrong"},
            )

        assert response.status_code == 401

    def test_wx_login_not_implemented(self, client) -> None:
        response = client.post("/api/v1/auth/wx-login", json={})
        assert response.status_code == 501
