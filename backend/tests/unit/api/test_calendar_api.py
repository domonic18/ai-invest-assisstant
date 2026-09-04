"""投资日历 API 端点与服务参数测试。"""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from app.api.v1.calendar import _parse_categories
from app.services.market.calendar_service import _cn_day_range

CN_TZ = ZoneInfo("Asia/Shanghai")


def _event_mock(**overrides: object) -> MagicMock:
    event = MagicMock()
    event.id = 1
    event.event_time = datetime(2026, 1, 28, 19, 0, tzinfo=timezone.utc)
    event.end_time = None
    event.title = "美联储 FOMC 利率决议"
    event.category = "央行动态"
    event.impact_markets = ["美股", "美债", "美元", "黄金"]
    event.source = "fomc"
    event.source_url = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
    event.related_symbols = ["US10Y", "US2Y", "DXY", "GC00Y"]
    for key, value in overrides.items():
        setattr(event, key, value)
    return event


@pytest.mark.unit
class TestCalendarHelpers:
    def test_parse_categories(self) -> None:
        assert _parse_categories("宏观, 央行动态") == ["宏观", "央行动态"]
        assert _parse_categories("宏观") == ["宏观"]
        assert _parse_categories(None) is None
        assert _parse_categories("") is None
        assert _parse_categories(" , ") is None

    def test_cn_day_range_converts_to_utc(self) -> None:
        start_dt, end_dt = _cn_day_range(date(2026, 1, 28), date(2026, 1, 30))
        assert start_dt == datetime(2026, 1, 27, 16, 0, tzinfo=timezone.utc)
        assert end_dt == datetime(2026, 1, 30, 16, 0, tzinfo=timezone.utc)

    def test_cn_day_range_single_day(self) -> None:
        start_dt, end_dt = _cn_day_range(date(2026, 9, 16), date(2026, 9, 16))
        assert start_dt == datetime(2026, 9, 15, 16, 0, tzinfo=timezone.utc)
        assert end_dt == datetime(2026, 9, 16, 16, 0, tzinfo=timezone.utc)
        # CN 9/16 当日事件（UTC 10:00 = 北京 18:00）落在区间内；
        # 18:00 UTC（北京 9/17 02:00）属于下一日历日，应落在区间外
        assert start_dt <= datetime(2026, 9, 16, 10, 0, tzinfo=timezone.utc) < end_dt
        assert datetime(2026, 9, 16, 18, 0, tzinfo=timezone.utc) >= end_dt


@pytest.mark.unit
class TestCalendarEndpoints:
    @patch("app.api.v1.calendar.calendar_service.list_events", new_callable=AsyncMock)
    async def test_list_events(self, mock_list: AsyncMock, client) -> None:
        mock_list.return_value = [_event_mock()]
        response = client.get("/api/v1/calendar/events", params={"start": "2026-01-28"})
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "美联储 FOMC 利率决议"
        assert data[0]["category"] == "央行动态"
        assert data[0]["impact_markets"] == ["美股", "美债", "美元", "黄金"]
        assert data[0]["related_symbols"] == ["US10Y", "US2Y", "DXY", "GC00Y"]
        mock_list.assert_awaited_once_with(
            mock_list.await_args.args[0],
            start=date(2026, 1, 28),
            end=None,
            categories=None,
            limit=200,
        )

    @patch("app.api.v1.calendar.calendar_service.list_events", new_callable=AsyncMock)
    async def test_list_events_with_range_and_categories(
        self, mock_list: AsyncMock, client
    ) -> None:
        mock_list.return_value = []
        response = client.get(
            "/api/v1/calendar/events",
            params={"start": "2026-01-01", "end": "2026-03-31", "categories": "宏观,央行动态"},
        )
        assert response.status_code == 200
        assert response.json() == []
        kwargs = mock_list.await_args.kwargs
        assert kwargs["start"] == date(2026, 1, 1)
        assert kwargs["end"] == date(2026, 3, 31)
        assert kwargs["categories"] == ["宏观", "央行动态"]

    @patch("app.api.v1.calendar.calendar_service.list_events", new_callable=AsyncMock)
    async def test_list_events_requires_start(
        self, mock_list: AsyncMock, client
    ) -> None:
        response = client.get("/api/v1/calendar/events")
        assert response.status_code == 422
        mock_list.assert_not_awaited()

    @patch("app.api.v1.calendar.calendar_service.list_events", new_callable=AsyncMock)
    async def test_list_events_limit_bounds(
        self, mock_list: AsyncMock, client
    ) -> None:
        assert (
            client.get(
                "/api/v1/calendar/events", params={"start": "2026-01-01", "limit": 0}
            ).status_code
            == 422
        )
        assert (
            client.get(
                "/api/v1/calendar/events", params={"start": "2026-01-01", "limit": 501}
            ).status_code
            == 422
        )
        mock_list.assert_not_awaited()

    @patch("app.api.v1.calendar.calendar_service.list_upcoming", new_callable=AsyncMock)
    async def test_list_upcoming(self, mock_upcoming: AsyncMock, client) -> None:
        mock_upcoming.return_value = [
            _event_mock(
                id=2,
                event_time=datetime(2026, 3, 18, 18, 0, tzinfo=timezone.utc),
                title="美国 CPI 通胀数据发布",
                category="宏观",
                source="bls",
            )
        ]
        response = client.get("/api/v1/calendar/events/upcoming", params={"limit": 5})
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == 2
        assert data[0]["title"] == "美国 CPI 通胀数据发布"
        mock_upcoming.assert_awaited_once_with(
            mock_upcoming.await_args.args[0], limit=5
        )
