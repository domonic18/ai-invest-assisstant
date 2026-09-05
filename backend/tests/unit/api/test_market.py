"""大盘 AI 复盘端点契约测试（鉴权 / 管理员 / 分区覆盖隔离）。"""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from app.dependencies import get_current_user
from app.main import app


@pytest.fixture
def normal_user():
    return type(
        "User",
        (object,),
        {"id": 1, "username": "user", "role": "user", "is_active": True},
    )()


@pytest.fixture
def admin_user():
    return type(
        "User",
        (object,),
        {"id": 2, "username": "admin", "role": "admin", "is_active": True},
    )()


@pytest.fixture
def auth_client(client, normal_user):
    app.dependency_overrides[get_current_user] = lambda: normal_user
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_client(client, admin_user):
    app.dependency_overrides[get_current_user] = lambda: admin_user
    yield client
    app.dependency_overrides.clear()


_TRADE_DATE = date(2026, 7, 17)

_SECTIONS = [
    {"key": "overview", "title": "AI 大盘综述", "content": "overview"},
    {"key": "technical_analysis", "title": "技术面分析", "content": "technical"},
    {"key": "capital_analysis", "title": "资金面分析", "content": "capital"},
    {"key": "emotion_analysis", "title": "情绪与连板分析", "content": "emotion"},
    {"key": "risk_advice", "title": "风险提示与策略建议", "content": "risk"},
]


def _mock_review(cached: bool, edited: bool) -> dict:
    return {
        "trade_date": _TRADE_DATE.isoformat(),
        "sections": _SECTIONS,
        "generated_at": "2026-07-17T16:30:00",
        "cached": cached,
        "edited": edited,
    }


@pytest.mark.unit
class TestGetAiReview:
    def test_requires_auth(self, client) -> None:
        response = client.get("/api/v1/market/ai-review")
        assert response.status_code == 401

    def test_returns_review_for_current_user(self, auth_client) -> None:
        with patch(
            "app.api.v1.market.market_review_service.get_market_review",
            AsyncMock(return_value=_mock_review(cached=True, edited=False)),
        ):
            response = auth_client.get("/api/v1/market/ai-review")

        assert response.status_code == 200
        body = response.json()
        assert body["cached"] is True
        assert [section["key"] for section in body["sections"]] == [
            "overview",
            "technical_analysis",
            "capital_analysis",
            "emotion_analysis",
            "risk_advice",
        ]

    def test_204_when_not_generated(self, auth_client) -> None:
        with patch(
            "app.api.v1.market.market_review_service.get_market_review",
            AsyncMock(return_value=None),
        ):
            response = auth_client.get("/api/v1/market/ai-review")

        assert response.status_code == 204
        assert response.content == b""


@pytest.mark.unit
class TestUpdateAiReview:
    def test_requires_auth(self, client) -> None:
        response = client.put(
            "/api/v1/market/ai-review",
            json={
                "trade_date": _TRADE_DATE.isoformat(),
                "section_key": "overview",
                "content": "updated",
            },
        )
        assert response.status_code == 401

    def test_user_saves_section_overlay(self, auth_client) -> None:
        with patch(
            "app.api.v1.market.market_review_service.update_market_review",
            AsyncMock(return_value=_mock_review(cached=True, edited=True)),
        ) as mock_update:
            response = auth_client.put(
                "/api/v1/market/ai-review",
                json={
                    "trade_date": _TRADE_DATE.isoformat(),
                    "section_key": "overview",
                    "content": "updated",
                },
            )

        assert response.status_code == 200
        assert response.json()["edited"] is True
        assert mock_update.await_count == 1
        assert mock_update.await_args.args[3:] == ("overview", "updated")

    def test_422_when_section_unknown(self, auth_client) -> None:
        from app.services.review.market_review_service import UnknownSectionError

        with patch(
            "app.api.v1.market.market_review_service.update_market_review",
            AsyncMock(side_effect=UnknownSectionError("未知的复盘分区：foo")),
        ):
            response = auth_client.put(
                "/api/v1/market/ai-review",
                json={
                    "trade_date": _TRADE_DATE.isoformat(),
                    "section_key": "foo",
                    "content": "updated",
                },
            )

        assert response.status_code == 422

    def test_422_when_content_empty(self, auth_client) -> None:
        response = auth_client.put(
            "/api/v1/market/ai-review",
            json={
                "trade_date": _TRADE_DATE.isoformat(),
                "section_key": "overview",
                "content": "",
            },
        )
        assert response.status_code == 422


@pytest.mark.unit
class TestGlobalIndicesEndpoint:
    def test_returns_enabled_quotes(self, client) -> None:
        with patch(
            "app.api.v1.market.global_index_service.get_global_index_quotes",
            AsyncMock(
                return_value=[
                    {
                        "index_code": "GC00Y",
                        "index_name": "COMEX黄金",
                        "close": 2650.5,
                        "change_pct": 0.83,
                        "trade_date": date(2026, 9, 2),
                    }
                ]
            ),
        ) as svc_mock:
            resp = client.get("/api/v1/market/global-indices")

        assert resp.status_code == 200
        body = resp.json()
        assert body[0]["index_code"] == "GC00Y"
        assert body[0]["close"] == 2650.5
        svc_mock.assert_awaited_once()

    def test_public_no_auth_required(self, client) -> None:
        with patch(
            "app.api.v1.market.global_index_service.get_global_index_quotes",
            AsyncMock(return_value=[]),
        ):
            resp = client.get("/api/v1/market/global-indices")

        assert resp.status_code == 200
        assert resp.json() == []
