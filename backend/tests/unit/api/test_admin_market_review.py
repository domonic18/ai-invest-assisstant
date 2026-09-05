"""后台复盘管理端点契约测试（鉴权绕过 + service mock）。"""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_admin_user, get_db
from app.main import app
from app.schemas.market import (
    AdminMarketReviewItem,
    AdminSectionDefinition,
    MarketReviewResponse,
    MarketReviewSection,
)
from app.services.review.market_review_generator import (
    NonTradingDayError,
    ReviewNotFoundError,
)

_TRADE_DATE = date(2026, 9, 4)
_GENERATED_AT = datetime(2026, 9, 5, 8, 0, tzinfo=timezone.utc)


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


def _review_response() -> MarketReviewResponse:
    return MarketReviewResponse(
        trade_date=_TRADE_DATE,
        sections=[
            MarketReviewSection(key="overview", title="AI 大盘综述", content="综述内容")
        ],
        model="anthropic/kimi",
        generated_at=_GENERATED_AT,
        cached=False,
        edited=False,
    )


def _list_item() -> AdminMarketReviewItem:
    return AdminMarketReviewItem(
        trade_date=_TRADE_DATE,
        model="anthropic/kimi",
        latency_ms=59000,
        generated_at=_GENERATED_AT,
        history_count=2,
        user_copy_count=1,
    )


def _patch_async(method: str, return_value=None, side_effect=None):
    return patch(
        f"app.api.v1.admin.market_review.AdminMarketReviewService.{method}",
        AsyncMock(return_value=return_value, side_effect=side_effect),
    )


def _patch_sync(method: str, return_value):
    return patch(
        f"app.api.v1.admin.market_review.AdminMarketReviewService.{method}",
        return_value=return_value,
    )


@pytest.mark.unit
class TestAdminMarketReviewEndpoints:
    def test_list_reviews(self, admin_client) -> None:
        with _patch_async("list_reviews", ([_list_item()], 1)):
            client, _ = admin_client
            response = client.get("/api/v1/admin/market-reviews/?page=1&page_size=10")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["trade_date"] == "2026-09-04"
        assert body["items"][0]["history_count"] == 2
        assert body["items"][0]["user_copy_count"] == 1

    def test_section_definitions_route_matches_before_date_param(
        self, admin_client
    ) -> None:
        definitions = [AdminSectionDefinition(key="overview", title="AI 大盘综述")]
        with _patch_sync("section_definitions", definitions):
            client, _ = admin_client
            response = client.get("/api/v1/admin/market-reviews/section-definitions")
        assert response.status_code == 200
        body = response.json()
        assert body[0]["key"] == "overview"
        assert body[0]["title"] == "AI 大盘综述"

    def test_create_manual_review(self, admin_client) -> None:
        with _patch_async("create_manual", _review_response()):
            client, _ = admin_client
            response = client.post(
                "/api/v1/admin/market-reviews/",
                json={
                    "trade_date": "2026-09-04",
                    "sections": {"overview": "综述", "risk_advice": "风险"},
                },
            )
        assert response.status_code == 201
        assert response.json()["trade_date"] == "2026-09-04"

    def test_create_rejects_non_trading_day(self, admin_client) -> None:
        with _patch_async(
            "create_manual", side_effect=NonTradingDayError("2026-09-05 不是交易日")
        ):
            client, _ = admin_client
            response = client.post(
                "/api/v1/admin/market-reviews/",
                json={"trade_date": "2026-09-05", "sections": {"overview": "x"}},
            )
        assert response.status_code == 400

    def test_create_maps_value_error_to_422(self, admin_client) -> None:
        with _patch_async(
            "create_manual", side_effect=ValueError("sections 缺少必填分区：overview")
        ):
            client, _ = admin_client
            response = client.post(
                "/api/v1/admin/market-reviews/",
                json={"trade_date": "2026-09-04", "sections": {}},
            )
        assert response.status_code == 422

    def test_get_detail(self, admin_client) -> None:
        with _patch_async("get_detail", _review_response()):
            client, _ = admin_client
            response = client.get("/api/v1/admin/market-reviews/2026-09-04")
        assert response.status_code == 200
        body = response.json()
        assert body["model"] == "anthropic/kimi"
        assert body["sections"][0]["key"] == "overview"

    def test_get_detail_404_when_missing(self, admin_client) -> None:
        with _patch_async(
            "get_detail", side_effect=ReviewNotFoundError("尚无 AI 复盘记录")
        ):
            client, _ = admin_client
            response = client.get("/api/v1/admin/market-reviews/2026-09-04")
        assert response.status_code == 404

    def test_update_sections(self, admin_client) -> None:
        with _patch_async("update_sections", _review_response()):
            client, _ = admin_client
            response = client.put(
                "/api/v1/admin/market-reviews/2026-09-04",
                json={"sections": {"overview": "修改后"}},
            )
        assert response.status_code == 200

    def test_update_maps_value_error_to_422(self, admin_client) -> None:
        with _patch_async(
            "update_sections", side_effect=ValueError("sections 缺少必填分区：risk_advice")
        ):
            client, _ = admin_client
            response = client.put(
                "/api/v1/admin/market-reviews/2026-09-04",
                json={"sections": {"overview": "x"}},
            )
        assert response.status_code == 422

    def test_delete_returns_204(self, admin_client) -> None:
        with _patch_async("delete", 4):
            client, _ = admin_client
            response = client.delete("/api/v1/admin/market-reviews/2026-09-04")
        assert response.status_code == 204

    def test_delete_404_when_nothing_deleted(self, admin_client) -> None:
        with _patch_async("delete", side_effect=ReviewNotFoundError("尚无 AI 复盘记录")):
            client, _ = admin_client
            response = client.delete("/api/v1/admin/market-reviews/2026-09-04")
        assert response.status_code == 404
