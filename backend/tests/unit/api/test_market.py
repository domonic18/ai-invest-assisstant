"""Unit tests for market AI review endpoints (auth / admin / overlay isolation)."""

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


@pytest.mark.unit
class TestGetAiReview:
    def test_requires_auth(self, client) -> None:
        response = client.get("/api/v1/market/ai-review")
        assert response.status_code == 401

    def test_returns_review_for_current_user(self, auth_client) -> None:
        mock_review = {
            "trade_date": _TRADE_DATE.isoformat(),
            "overview": "overview",
            "emotion_analysis": "emotion",
            "capital_analysis": "capital",
            "risk_advice": "risk",
            "generated_at": "2026-07-17T16:30:00",
            "cached": True,
            "edited": False,
        }
        with patch(
            "app.api.v1.market.market_review_service.get_market_review",
            AsyncMock(return_value=mock_review),
        ):
            response = auth_client.get("/api/v1/market/ai-review")

        assert response.status_code == 200
        assert response.json()["cached"] is True

    def test_404_when_not_generated(self, auth_client) -> None:
        with patch(
            "app.api.v1.market.market_review_service.get_market_review",
            AsyncMock(return_value=None),
        ):
            response = auth_client.get("/api/v1/market/ai-review")

        assert response.status_code == 404


@pytest.mark.unit
class TestGenerateAiReview:
    def test_requires_admin(self, auth_client) -> None:
        response = auth_client.post(
            "/api/v1/market/ai-review",
            json={"trade_date": _TRADE_DATE.isoformat(), "regenerate": False},
        )
        assert response.status_code == 403

    def test_admin_triggers_generation(self, admin_client) -> None:
        mock_review = {
            "trade_date": _TRADE_DATE.isoformat(),
            "overview": "overview",
            "emotion_analysis": "emotion",
            "capital_analysis": "capital",
            "risk_advice": "risk",
            "generated_at": "2026-07-17T16:30:00",
            "cached": False,
            "edited": False,
        }
        with patch(
            "app.api.v1.market.market_review_service.generate_market_review",
            AsyncMock(return_value=mock_review),
        ):
            response = admin_client.post(
                "/api/v1/market/ai-review",
                json={"trade_date": _TRADE_DATE.isoformat(), "regenerate": True},
            )

        assert response.status_code == 200
        assert response.json()["cached"] is False


@pytest.mark.unit
class TestUpdateAiReview:
    def test_requires_auth(self, client) -> None:
        response = client.put(
            "/api/v1/market/ai-review",
            json={
                "trade_date": _TRADE_DATE.isoformat(),
                "overview": "o",
                "emotion_analysis": "e",
                "capital_analysis": "c",
                "risk_advice": "r",
            },
        )
        assert response.status_code == 401

    def test_user_saves_overlay(self, auth_client) -> None:
        mock_review = {
            "trade_date": _TRADE_DATE.isoformat(),
            "overview": "updated",
            "emotion_analysis": "emotion",
            "capital_analysis": "capital",
            "risk_advice": "risk",
            "generated_at": "2026-07-17T16:30:00",
            "cached": True,
            "edited": True,
        }
        with patch(
            "app.api.v1.market.market_review_service.update_market_review",
            AsyncMock(return_value=mock_review),
        ):
            response = auth_client.put(
                "/api/v1/market/ai-review",
                json={
                    "trade_date": _TRADE_DATE.isoformat(),
                    "overview": "updated",
                    "emotion_analysis": "emotion",
                    "capital_analysis": "capital",
                    "risk_advice": "risk",
                },
            )

        assert response.status_code == 200
        assert response.json()["edited"] is True
