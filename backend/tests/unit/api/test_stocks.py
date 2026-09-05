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
    def test_ai_analysis_status_none_when_not_generated(self, auth_client) -> None:
        with (
            patch(
                "app.api.v1.stocks.trade_calendar_service.resolve_latest_trade_date",
                AsyncMock(return_value=date(2026, 9, 1)),
            ),
            patch(
                "app.api.v1.stocks.trade_calendar_service.is_trading_day",
                AsyncMock(return_value=True),
            ),
            patch(
                "app.api.v1.stocks.stock_daily_analysis_service.get_stock_analysis",
                AsyncMock(return_value=None),
            ) as get_mock,
            patch(
                "app.api.v1.stocks.stock_daily_analysis_service.is_generation_running",
                AsyncMock(return_value=False),
            ),
        ):
            resp = auth_client.get("/api/v1/stocks/600519/ai-analysis")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "none"
        assert body["data"] is None
        assert body["trade_date"] == "2026-09-01"
        _, kwargs = get_mock.await_args
        assert kwargs["trade_date"] == date(2026, 9, 1)

    def test_ai_analysis_status_running_when_lock_held(self, auth_client) -> None:
        with (
            patch(
                "app.api.v1.stocks.trade_calendar_service.resolve_latest_trade_date",
                AsyncMock(return_value=date(2026, 9, 1)),
            ),
            patch(
                "app.api.v1.stocks.trade_calendar_service.is_trading_day",
                AsyncMock(return_value=True),
            ),
            patch(
                "app.api.v1.stocks.stock_daily_analysis_service.get_stock_analysis",
                AsyncMock(return_value=None),
            ),
            patch(
                "app.api.v1.stocks.stock_daily_analysis_service.is_generation_running",
                AsyncMock(return_value=True),
            ) as lock_mock,
        ):
            resp = auth_client.get("/api/v1/stocks/600519/ai-analysis")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "running"
        assert body["data"] is None
        lock_mock.assert_awaited_once_with("600519", date(2026, 9, 1))

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
                "app.api.v1.stocks.trade_calendar_service.is_trading_day",
                AsyncMock(return_value=True),
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
        assert body["status"] == "ready"
        assert body["trade_date"] == "2026-08-29"
        assert body["data"]["stock_code"] == "600519"
        assert body["data"]["stock_name"] == "贵州茅台"
        assert body["data"]["trade_date"] == "2026-08-29"
        assert body["data"]["model"] == "openai/gpt-4o"
        assert body["data"]["cached"] is True
        assert body["data"]["sections"][0]["key"] == "intraday_review"
        assert body["data"]["sections"][0]["content"] == "内容"
        _, kwargs = get_mock.await_args
        assert kwargs["trade_date"] == date(2026, 8, 29)

    def test_ai_analysis_clamps_non_trading_date(self, auth_client) -> None:
        """周六显式查询归位到周五：查询与响应均用归位后的有效交易日。"""
        analysis = StockAiAnalysisResponse(
            stock_code="601678",
            stock_name="滨化股份",
            trade_date=date(2026, 9, 4),
            model="openai/gpt-4o",
            generated_at=datetime(2026, 9, 5, 3, 0, tzinfo=timezone.utc),
            cached=True,
            sections=[
                StockAiAnalysisSection(key="intraday_review", title="盘面解读", content="内容")
            ],
        )
        with (
            patch(
                "app.api.v1.stocks.trade_calendar_service.is_trading_day",
                AsyncMock(return_value=False),
            ),
            patch(
                "app.api.v1.stocks.trade_calendar_service.resolve_trade_date_on_or_before",
                AsyncMock(return_value=date(2026, 9, 4)),
            ) as clamp_mock,
            patch(
                "app.api.v1.stocks.stock_daily_analysis_service.get_stock_analysis",
                AsyncMock(return_value=analysis),
            ) as get_mock,
        ):
            resp = auth_client.get(
                "/api/v1/stocks/601678/ai-analysis", params={"trade_date": "2026-09-05"}
            )

        clamp_mock.assert_awaited_once()
        assert clamp_mock.await_args.args[-1] == date(2026, 9, 5)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ready"
        assert body["trade_date"] == "2026-09-04"
        assert body["data"]["trade_date"] == "2026-09-04"
        _, kwargs = get_mock.await_args
        assert kwargs["trade_date"] == date(2026, 9, 4)

    def test_ai_analysis_requires_auth(self, client) -> None:
        resp = client.get("/api/v1/stocks/600519/ai-analysis")
        assert resp.status_code in (401, 403)
