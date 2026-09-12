"""问财直查端点契约测试（鉴权 / 502 映射 / wire 形状）。"""

from unittest.mock import AsyncMock, patch

import pytest

from app.dependencies import get_current_user
from app.main import app
from app.services.market.iwencai_service import IwencaiError

pytestmark = pytest.mark.unit


@pytest.fixture
def user():
    return type(
        "User", (object,), {"id": 1, "username": "user", "role": "user", "is_active": True}
    )()


@pytest.fixture
def auth_client(client, user):
    app.dependency_overrides[get_current_user] = lambda: user
    yield client
    app.dependency_overrides.clear()


def _screen_payload() -> dict:
    return {
        "query": "市盈率<20",
        "total": 1,
        "truncated": False,
        "columns": ["最新价"],
        "stocks": [{"stockCode": "000001", "stockName": "平安银行", "最新价": 12.1}],
        "chunks_info": [{"clause": "市盈率<20"}],
    }


def test_query_requires_auth(client) -> None:
    response = client.post(
        "/api/v1/screening/query", json={"query": "市盈率<20", "limit": 50}
    )
    assert response.status_code == 401


def test_query_success_shape(auth_client) -> None:
    with patch(
        "app.api.v1.screening.iwencai_service.screen",
        AsyncMock(return_value=_screen_payload()),
    ):
        response = auth_client.post(
            "/api/v1/screening/query", json={"query": "市盈率<20", "limit": 50}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "市盈率<20"
    assert body["total"] == 1
    assert body["truncated"] is False
    assert body["columns"] == ["最新价"]
    # chunks_info 是 agent 调试字段，不进直查 wire
    assert "chunks_info" not in body
    assert body["stocks"][0]["stockCode"] == "000001"
    assert body["stocks"][0]["最新价"] == 12.1


def test_query_maps_gateway_error_to_502(auth_client) -> None:
    with patch(
        "app.api.v1.screening.iwencai_service.screen",
        AsyncMock(side_effect=IwencaiError("问财网关返回错误：unauthorized")),
    ):
        response = auth_client.post(
            "/api/v1/screening/query", json={"query": "市盈率<20"}
        )

    assert response.status_code == 502
    assert "unauthorized" in response.json()["detail"]


def test_query_rejects_blank_and_oversized(auth_client) -> None:
    for payload in [{"query": ""}, {"query": "x" * 501}, {"query": "ok", "limit": 0}]:
        response = auth_client.post("/api/v1/screening/query", json=payload)
        assert response.status_code == 422
