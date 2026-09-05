"""后台 AI 结果管理端点契约测试（鉴权绕过 + service mock）。"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import NotFoundError, UnprocessableEntityError
from app.dependencies import get_current_admin_user, get_db
from app.main import app
from app.schemas.ai_result import (
    AdminAiResultDetail,
    AdminAiResultItem,
    AdminAiResultKeyField,
)

_ROW_ID = 7
_CREATED_AT = datetime(2026, 9, 5, 8, 0, tzinfo=timezone.utc)


@pytest.fixture
def admin_client(client) -> tuple[TestClient, AsyncMock]:
    """返回已绕过管理员认证并注入 mock session 的客户端。"""
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


def _item() -> AdminAiResultItem:
    return AdminAiResultItem(
        id=_ROW_ID,
        skill_id="market-daily-review",
        key_fields=[AdminAiResultKeyField(name="trade_date", label="交易日", value="2026-09-04")],
        model="anthropic/kimi",
        latency_ms=59000,
        status="success",
        created_at=_CREATED_AT,
        history_count=2,
        regenerate_prompt="请重新生成 2026-09-04 的大盘每日复盘",
    )


def _detail() -> AdminAiResultDetail:
    return AdminAiResultDetail(
        **_item().model_dump(),
        error_msg=None,
        structured_output={"trade_date": "2026-09-04", "sections": {}},
    )


def _patch_async(method: str, return_value=None, side_effect=None):
    return patch(
        f"app.api.v1.admin.ai_results.AdminAiResultService.{method}",
        AsyncMock(return_value=return_value, side_effect=side_effect),
    )


def _patch_sync(method: str, return_value):
    return patch(
        f"app.api.v1.admin.ai_results.AdminAiResultService.{method}",
        return_value=return_value,
    )


@pytest.mark.unit
class TestAdminAiResultEndpoints:
    def test_skills_route_matches_before_id_param(self, admin_client) -> None:
        from app.services.admin.ai_results import AdminAiResultService

        with _patch_sync("list_skills", AdminAiResultService.list_skills()):
            client, _ = admin_client
            response = client.get("/api/v1/admin/ai-results/skills")
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 4
        assert {item["skill_id"] for item in body} >= {
            "market-daily-review",
            "limit-up-review",
            "stock-daily-analysis",
            "industry-chain-analysis",
        }

    def test_list_results(self, admin_client) -> None:
        with _patch_async("list_results", ([_item()], 1)):
            client, _ = admin_client
            response = client.get(
                "/api/v1/admin/ai-results/?skill_id=market-daily-review&page=1&page_size=10"
            )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == _ROW_ID
        assert body["items"][0]["key_fields"][0]["value"] == "2026-09-04"
        assert body["items"][0]["history_count"] == 2

    def test_list_results_requires_skill_id(self, admin_client) -> None:
        client, _ = admin_client
        response = client.get("/api/v1/admin/ai-results/")
        assert response.status_code == 422

    def test_list_results_rejects_unknown_skill(self, admin_client) -> None:
        with _patch_async(
            "list_results", side_effect=UnprocessableEntityError("未纳管的 AI skill")
        ):
            client, _ = admin_client
            response = client.get("/api/v1/admin/ai-results/?skill_id=mystery")
        assert response.status_code == 422

    def test_get_detail(self, admin_client) -> None:
        with _patch_async("get_detail", _detail()):
            client, _ = admin_client
            response = client.get(f"/api/v1/admin/ai-results/{_ROW_ID}")
        assert response.status_code == 200
        body = response.json()
        assert body["structured_output"]["trade_date"] == "2026-09-04"
        assert body["model"] == "anthropic/kimi"

    def test_get_detail_404_when_missing(self, admin_client) -> None:
        with _patch_async("get_detail", side_effect=NotFoundError("不存在")):
            client, _ = admin_client
            response = client.get("/api/v1/admin/ai-results/999")
        assert response.status_code == 404

    def test_delete_returns_204(self, admin_client) -> None:
        with _patch_async("delete", 4):
            client, _ = admin_client
            response = client.delete(f"/api/v1/admin/ai-results/{_ROW_ID}")
        assert response.status_code == 204

    def test_delete_404_when_missing(self, admin_client) -> None:
        with _patch_async("delete", side_effect=NotFoundError("不存在")):
            client, _ = admin_client
            response = client.delete("/api/v1/admin/ai-results/999")
        assert response.status_code == 404

    def test_requires_admin_authentication(self, client) -> None:
        response = client.get("/api/v1/admin/ai-results/skills")
        assert response.status_code in (401, 403)
