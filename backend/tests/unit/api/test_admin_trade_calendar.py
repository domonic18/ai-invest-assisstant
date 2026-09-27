"""交易日历管理端点测试：年度视图 / 单日人工覆盖 / 种子刷新 / 历史日拒绝。"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import BadRequestError
from app.dependencies import get_current_admin_user, get_db
from app.main import app
from app.schemas.trade_calendar import (
    TradeCalendarCoverage,
    TradeCalendarDayResponse,
    TradeCalendarYearResponse,
)


def _year_response() -> TradeCalendarYearResponse:
    return TradeCalendarYearResponse(
        year=2026,
        days=[
            TradeCalendarDayResponse(
                calendar_date=date(2026, 10, 1),
                is_trading=False,
                source="seed",
                remark=None,
            ),
            TradeCalendarDayResponse(
                calendar_date=date(2026, 10, 10),
                is_trading=True,
                source="manual",
                remark="国庆调休上班",
            ),
        ],
        coverage=TradeCalendarCoverage(
            min_date=date(2026, 1, 1),
            max_date=date(2026, 12, 31),
            trading_days=244,
            non_trading_days=121,
        ),
    )


@pytest.fixture
def admin_client(client) -> tuple[TestClient, AsyncMock]:
    """绕过管理员认证并注入 mock session。"""
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


@pytest.mark.unit
class TestTradeCalendarEndpoints:
    @patch("app.api.v1.admin.trade_calendar.trade_calendar_admin.get_year")
    def test_get_year_wire_shape(self, mock_get_year, admin_client) -> None:
        mock_get_year.return_value = _year_response()
        client, _ = admin_client
        response = client.get("/api/v1/admin/trade-calendar", params={"year": 2026})
        assert response.status_code == 200
        body = response.json()
        assert body["year"] == 2026
        assert body["coverage"]["minDate"] == "2026-01-01"
        assert body["coverage"]["tradingDays"] == 244
        assert body["days"][1]["calendarDate"] == "2026-10-10"
        assert body["days"][1]["source"] == "manual"
        mock_get_year.assert_awaited_once()

    @patch("app.api.v1.admin.trade_calendar.trade_calendar_admin.set_day")
    def test_update_day(self, mock_set_day, admin_client) -> None:
        mock_set_day.return_value = TradeCalendarDayResponse(
            calendar_date=date(2026, 10, 10),
            is_trading=True,
            source="manual",
            remark="国庆调休上班",
        )
        client, _ = admin_client
        response = client.put(
            "/api/v1/admin/trade-calendar/2026-10-10",
            json={"isTrading": True, "remark": "国庆调休上班"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["isTrading"] is True
        assert body["source"] == "manual"
        mock_set_day.assert_awaited_once()

    @patch("app.api.v1.admin.trade_calendar.trade_calendar_admin.set_day")
    def test_update_past_day_returns_400(self, mock_set_day, admin_client) -> None:
        mock_set_day.side_effect = BadRequestError("不可修改历史日期的日历口径")
        client, _ = admin_client
        response = client.put(
            "/api/v1/admin/trade-calendar/2026-01-01",
            json={"isTrading": True},
        )
        assert response.status_code == 400
        assert "历史日期" in response.json()["detail"]

    @patch("app.api.v1.admin.trade_calendar.trade_calendar_admin.seed")
    def test_seed(self, mock_seed, admin_client) -> None:
        mock_seed.return_value = ([2026, 2027], 730)
        client, _ = admin_client
        response = client.post("/api/v1/admin/trade-calendar/seed", json={})
        assert response.status_code == 200
        body = response.json()
        assert body["years"] == [2026, 2027]
        assert body["written"] == 730

    @patch("app.api.v1.admin.trade_calendar.trade_calendar_admin.seed")
    def test_seed_with_explicit_years(self, mock_seed, admin_client) -> None:
        mock_seed.return_value = ([2025], 365)
        client, mock_session = admin_client
        response = client.post(
            "/api/v1/admin/trade-calendar/seed", json={"years": [2025]}
        )
        assert response.status_code == 200
        assert response.json()["years"] == [2025]
        mock_seed.assert_awaited_once_with(mock_session, [2025])
