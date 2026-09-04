"""基础可达性测试：确认被测栈各入口正常。"""

import httpx


class TestHealth:
    def test_backend_health(self, client: httpx.Client) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_frontend_served(self, client: httpx.Client) -> None:
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_openapi_available(self, client: httpx.Client) -> None:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        assert response.json()["info"]["title"]
