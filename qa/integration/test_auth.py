"""认证与权限回归：登录、受保护端点鉴权。"""

import httpx

from integration.conftest import API_V1


class TestAuth:
    def test_login_success(self, admin_token: str) -> None:
        assert admin_token

    def test_login_wrong_password_rejected(self, client: httpx.Client) -> None:
        response = client.post(
            f"{API_V1}/auth/login",
            data={"username": "qa_admin", "password": "wrong-password"},
        )
        assert response.status_code == 401

    def test_admin_endpoint_requires_token(self, client: httpx.Client) -> None:
        response = client.get(f"{API_V1}/admin/collector/logs")
        assert response.status_code == 401

    def test_admin_endpoint_accepts_admin_token(
        self, admin_client: httpx.Client
    ) -> None:
        response = admin_client.get(f"{API_V1}/admin/collector/logs")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
