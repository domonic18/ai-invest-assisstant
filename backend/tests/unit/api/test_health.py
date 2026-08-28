"""健康检查端点契约测试。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.mark.unit
class TestHealth:
    def test_health_check(self) -> None:
        with TestClient(app) as client:
            response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
