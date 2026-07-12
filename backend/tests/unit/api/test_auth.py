from unittest.mock import patch

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

        with patch("app.api.v1.auth.user_service.get_user_by_username", return_value=None):
            with patch("app.api.v1.auth.user_service.get_user_by_email", return_value=None):
                with patch("app.api.v1.auth.user_service.create_user", return_value=mock_user):
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
        with patch("app.api.v1.auth.user_service.authenticate_user", return_value=None):
            response = client.post(
                "/api/v1/auth/login",
                json={"username": "tester", "password": "wrong"},
            )

        assert response.status_code == 401

    def test_wx_login_not_implemented(self, client) -> None:
        response = client.post("/api/v1/auth/wx-login", json={})
        assert response.status_code == 501
