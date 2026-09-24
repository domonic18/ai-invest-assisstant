"""ai_quota_gate 依赖契约单测：入口预检（耗尽 429）+ meter_scope 上下文对端点可见。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.exceptions import AppError, QuotaExhaustedError
from app.dependencies import ai_quota_gate, get_current_user
from app.main import app_error_handler
from app.services.quota.constants import FEATURE_PAGE
from app.services.quota.context import current_meter_context

pytestmark = pytest.mark.unit


def _build_client() -> TestClient:
    """独立 stub 应用：真实 gate 依赖 + 真实 AppError handler。"""
    app = FastAPI()
    app.add_exception_handler(AppError, app_error_handler)

    @app.get("/ping")
    async def ping(user=Depends(ai_quota_gate(FEATURE_PAGE))) -> dict:
        ctx = current_meter_context()
        return {
            "user_id": user.id,
            "meter_user_id": ctx.user_id if ctx else None,
            "meter_feature": ctx.feature if ctx else None,
        }

    stub_user = SimpleNamespace(id=7, username="tester", role="user")
    app.dependency_overrides[get_current_user] = lambda: stub_user
    return TestClient(app)


def test_gate_wraps_meter_context() -> None:
    """gate 的 yield 依赖与端点同任务执行：ContextVar 上下文端点内可见。"""
    client = _build_client()
    with patch(
        "app.services.quota.quota_service.precheck", AsyncMock()
    ) as precheck:
        response = client.get("/ping")

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == 7
    assert body["meter_user_id"] == 7
    assert body["meter_feature"] == FEATURE_PAGE
    precheck.assert_awaited_once_with(7)


def test_gate_exhausted_quota_maps_429() -> None:
    """预检拒绝经真实 AppError handler 转换为 429。"""
    client = _build_client()
    exhausted = AsyncMock(side_effect=QuotaExhaustedError())
    with patch("app.services.quota.quota_service.precheck", exhausted):
        response = client.get("/ping")

    assert response.status_code == 429
    assert "配额" in response.json()["detail"]
