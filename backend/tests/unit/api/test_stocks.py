"""股票搜索/详情 API 端点契约测试。"""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.stock import StockAiAnalysisResponse, StockAiAnalysisSection


@pytest.mark.unit
class TestStocksEndpoints:
    def test_search_stocks(self, client) -> None:
        mock_items = [
            type(
                "StockBasic",
                (object,),
                {
                    "id": 1,
                    "stock_code": "000001",
                    "stock_name": "平安银行",
                    "market": "sz",
                    "industry_level_1": "银行",
                    "industry_level_2": "股份制银行",
                    "industry_level_3": "银行III",
                    "listing_date": None,
                    "full_name": None,
                    "legal_person": None,
                    "website": None,
                    "registered_capital": None,
                    "business_scope": None,
                    "province": None,
                    "city": None,
                },
            )()
        ]

        with patch("app.api.v1.stocks.stock_service.search_stocks", return_value=mock_items):
            response = client.get("/api/v1/stocks/search?q=000001")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["stock_code"] == "000001"

    def test_get_stock_not_found(self, client) -> None:
        with patch("app.api.v1.stocks.stock_service.get_stock_by_code", return_value=None):
            response = client.get("/api/v1/stocks/999999")

        assert response.status_code == 404


@pytest.fixture
def normal_user():
    return type(
        "User",
        (object,),
        {"id": 1, "username": "user", "role": "user", "is_active": True},
    )()


@pytest.fixture
def auth_client(client, normal_user):
    from app.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: normal_user
    yield client
    app.dependency_overrides.clear()


@pytest.mark.unit
class TestStockAiAnalysisEndpoint:
    def test_ai_analysis_204_when_not_generated(self, auth_client) -> None:
        with (
            patch(
                "app.api.v1.stocks.trade_calendar_service.resolve_latest_trade_date",
                AsyncMock(return_value=date(2026, 9, 1)),
            ),
            patch(
                "app.api.v1.stocks.stock_daily_analysis_service.get_stock_analysis",
                AsyncMock(return_value=None),
            ) as get_mock,
        ):
            resp = auth_client.get("/api/v1/stocks/600519/ai-analysis")

        assert resp.status_code == 204
        _, kwargs = get_mock.await_args
        assert kwargs["trade_date"] == date(2026, 9, 1)

    def test_ai_analysis_200_with_sections(self, auth_client) -> None:
        analysis = StockAiAnalysisResponse(
            stock_code="600519",
            stock_name="贵州茅台",
            trade_date=date(2026, 8, 29),
            model="openai/gpt-4o",
            generated_at=datetime(2026, 8, 29, 8, 40, tzinfo=timezone.utc),
            cached=True,
            sections=[
                StockAiAnalysisSection(key="intraday_review", title="盘面解读", content="内容")
            ],
        )
        with (
            patch(
                "app.api.v1.stocks.trade_calendar_service.resolve_latest_trade_date",
                AsyncMock(return_value=date(2026, 9, 1)),
            ),
            patch(
                "app.api.v1.stocks.stock_daily_analysis_service.get_stock_analysis",
                AsyncMock(return_value=analysis),
            ) as get_mock,
        ):
            resp = auth_client.get(
                "/api/v1/stocks/600519/ai-analysis", params={"trade_date": "2026-08-29"}
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["stock_code"] == "600519"
        assert body["stock_name"] == "贵州茅台"
        assert body["trade_date"] == "2026-08-29"
        assert body["model"] == "openai/gpt-4o"
        assert body["cached"] is True
        assert body["sections"][0]["key"] == "intraday_review"
        assert body["sections"][0]["content"] == "内容"
        _, kwargs = get_mock.await_args
        assert kwargs["trade_date"] == date(2026, 8, 29)

    def test_ai_analysis_requires_auth(self, client) -> None:
        resp = client.get("/api/v1/stocks/600519/ai-analysis")
        assert resp.status_code in (401, 403)
