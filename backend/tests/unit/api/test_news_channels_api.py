"""资讯渠道监控端点契约测试（鉴权 / camelCase wire）。"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.dependencies import get_current_user
from app.main import app
from app.schemas.news import (
    NewsChannelResponse,
    NewsChannelsResponse,
    NewsStatsResponse,
)


@pytest.fixture
def normal_user():
    return type(
        "User",
        (object,),
        {"id": 3, "username": "user", "role": "user", "is_active": True},
    )()


@pytest.fixture
def auth_client(client, normal_user):
    app.dependency_overrides[get_current_user] = lambda: normal_user
    yield client
    app.dependency_overrides.clear()


@pytest.mark.unit
class TestNewsChannelsEndpoint:
    def test_requires_auth(self, client) -> None:
        resp = client.get("/api/v1/news/channels")
        assert resp.status_code in (401, 403)

    @patch(
        "app.api.v1.news.news_channel_service.get_channels_status",
        new_callable=AsyncMock,
    )
    def test_returns_channels_and_stats(self, mock_status: AsyncMock, auth_client) -> None:
        mock_status.return_value = NewsChannelsResponse(
            channels=[
                NewsChannelResponse(
                    key="cls_telegraph",
                    name="财联社电报",
                    status="live",
                    status_text="LIVE 采集中",
                    poll_desc="10s 增量轮询 · 驻留进程",
                    today_count=120,
                    last_updated_at=datetime(2026, 9, 8, 3, 55, tzinfo=timezone.utc),
                    lag_seconds=300,
                )
            ],
            stats=NewsStatsResponse(today_total=100, scored_count=80, high_count=12),
        )
        resp = auth_client.get("/api/v1/news/channels")

        assert resp.status_code == 200
        data = resp.json()
        channel = data["channels"][0]
        assert channel["key"] == "cls_telegraph"
        assert channel["status"] == "live"
        assert channel["statusText"] == "LIVE 采集中"
        assert channel["pollDesc"] == "10s 增量轮询 · 驻留进程"
        assert channel["todayCount"] == 120
        assert channel["lastUpdatedAt"] == "2026-09-08T03:55:00Z"
        assert channel["lagSeconds"] == 300
        assert data["stats"] == {"todayTotal": 100, "scoredCount": 80, "highCount": 12}
