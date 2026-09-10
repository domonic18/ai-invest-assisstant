"""资讯中心迭代 4 端点契约测试：focus/stories/topics/subscriptions（鉴权 + camelCase wire）。"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.dependencies import get_current_user
from app.main import app

_TS = datetime(2026, 9, 8, 3, 0, tzinfo=timezone.utc)


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


def _focus_payload() -> dict:
    return {
        "highlights": [
            {
                "source": "cls_telegraph",
                "item_id": "1",
                "title": "央行降准",
                "content": "降准落地",
                "publish_time": _TS,
                "score": 85,
                "factors": {
                    "impact_scope": 90,
                    "certainty": 80,
                    "related_count": 30,
                },
                "reason": "重磅",
            }
        ],
        "storylines": [
            {
                "id": 12,
                "title": "降准故事线",
                "summary": None,
                "status": "tracking",
                "origin": "ai",
                "report_count": 6,
                "first_seen_at": _TS,
                "last_seen_at": _TS,
                "latest_brief": "官宣降准",
                "nodes": [{"time": _TS.isoformat(), "brief": "官宣降准"}],
                "user_action": None,
            }
        ],
    }


@pytest.mark.unit
class TestFocusEndpoints:
    def test_requires_auth(self, client) -> None:
        assert client.get("/api/v1/news/focus").status_code in (401, 403)

    @patch(
        "app.api.v1.news.storyline_service.get_focus",
        new_callable=AsyncMock,
    )
    def test_focus_wire_camel_case(
        self, mock_focus: AsyncMock, auth_client
    ) -> None:
        from app.schemas.news import FocusResponse

        mock_focus.return_value = FocusResponse.model_validate(_focus_payload())
        resp = auth_client.get("/api/v1/news/focus")

        assert resp.status_code == 200
        data = resp.json()
        item = data["highlights"][0]
        assert item["itemId"] == "1"
        assert item["publishTime"] == "2026-09-08T03:00:00Z"
        assert item["factors"]["impactScope"] == 90
        line = data["storylines"][0]
        assert line["reportCount"] == 6
        assert line["userAction"] is None
        assert line["nodes"][0]["brief"] == "官宣降准"

    @patch(
        "app.api.v1.news.storyline_service.set_user_action",
        new_callable=AsyncMock,
    )
    def test_story_stop_returns_204(
        self, mock_action: AsyncMock, auth_client
    ) -> None:
        resp = auth_client.post("/api/v1/news/stories/12/stop")
        assert resp.status_code == 204
        assert mock_action.await_args.kwargs["action"] == "stopped"
        assert mock_action.await_args.kwargs["user_id"] == 3


@pytest.mark.unit
class TestTopicsEndpoint:
    @patch(
        "app.api.v1.news.topic_service.get_topics",
        new_callable=AsyncMock,
    )
    def test_topics_session_query_passthrough(
        self, mock_topics: AsyncMock, auth_client
    ) -> None:
        mock_topics.return_value = {
            "trade_date": "2026-09-08",
            "session": "intraday",
            "topics": [
                {
                    "title": "存储芯片涨价",
                    "sentiment": "利好",
                    "votes": {"bullish": 5, "bearish": 0, "neutral": 1},
                    "news_count": 6,
                    "channel_counts": {"cls_telegraph": 6},
                    "heat": 70.0,
                    "factors": {
                        "news_count": 6,
                        "sector_change_pct": 5.0,
                        "fund_flow_net": 5e8,
                        "as_of_trade_date": "2026-09-07",
                    },
                    "sectors": [
                        {"name": "半导体", "change_pct": 5.0, "fund_flow": 5e8}
                    ],
                    "chain": [
                        {
                            "event": "海外大厂减产",
                            "link": "供给收缩",
                            "stocks": [
                                {"name": "中微公司", "code": "688012", "change_pct": 3.2}
                            ],
                        }
                    ],
                    "item_ids": ["1", "2", "3"],
                }
            ],
            "wordcloud": [{"word": "存储", "count": 3}],
            "generated_at": _TS,
        }
        resp = auth_client.get("/api/v1/news/topics", params={"session": "intraday"})

        assert resp.status_code == 200
        assert mock_topics.await_args.kwargs["session_key"] == "intraday"
        data = resp.json()
        topic = data["topics"][0]
        assert topic["newsCount"] == 6
        assert topic["factors"]["asOfTradeDate"] == "2026-09-07"  # T-1 标注
        assert topic["sectors"][0]["changePct"] == 5.0
        assert data["wordcloud"][0]["word"] == "存储"

    @patch(
        "app.api.v1.news.topic_service.get_topics",
        new_callable=AsyncMock,
    )
    def test_topics_invalid_session_falls_back_post(
        self, mock_topics: AsyncMock, auth_client
    ) -> None:
        mock_topics.return_value = {
            "trade_date": "2026-09-08",
            "session": "post",
            "topics": [],
            "wordcloud": [],
            "generated_at": None,
        }
        resp = auth_client.get("/api/v1/news/topics", params={"session": "bogus"})

        assert resp.status_code == 200
        assert mock_topics.await_args.kwargs["session_key"] == "post"


@pytest.mark.unit
class TestSubscriptionEndpoints:
    def test_requires_auth(self, client) -> None:
        assert client.get("/api/v1/news/subscriptions").status_code in (401, 403)

    @patch(
        "app.api.v1.news.subscription_service.with_hit_stats",
        new_callable=AsyncMock,
    )
    @patch(
        "app.api.v1.news.subscription_service.create",
        new_callable=AsyncMock,
    )
    def test_create_subscription(
        self,
        mock_create: AsyncMock,
        mock_stats: AsyncMock,
        auth_client,
    ) -> None:
        from types import SimpleNamespace

        mock_create.return_value = SimpleNamespace(id=7)
        mock_stats.return_value = {
            "id": 7,
            "keyword": "存储",
            "channels": None,
            "push_enabled": False,
            "enabled": True,
            "created_at": _TS,
            "updated_at": _TS,
            "hit_count": 0,
            "last_hit_at": None,
        }
        resp = auth_client.post(
            "/api/v1/news/subscriptions", json={"keyword": "存储"}
        )

        assert resp.status_code == 201
        assert mock_create.await_args.kwargs["keyword"] == "存储"
        data = resp.json()
        assert data["keyword"] == "存储"
        assert data["hitCount"] == 0
        assert data["pushEnabled"] is False

    @patch(
        "app.api.v1.news.subscription_service.update",
        new_callable=AsyncMock,
        side_effect=NotFoundError("订阅不存在"),
    )
    def test_update_foreign_subscription_404(
        self, mock_update: AsyncMock, auth_client
    ) -> None:
        resp = auth_client.patch(
            "/api/v1/news/subscriptions/999", json={"enabled": False}
        )
        assert resp.status_code == 404

    @patch(
        "app.api.v1.news.subscription_service.create",
        new_callable=AsyncMock,
        side_effect=ConflictError("该关键词已订阅"),
    )
    def test_create_duplicate_409(
        self, mock_create: AsyncMock, auth_client
    ) -> None:
        resp = auth_client.post(
            "/api/v1/news/subscriptions", json={"keyword": "存储"}
        )
        assert resp.status_code == 409

    @patch(
        "app.api.v1.news.subscription_service.delete",
        new_callable=AsyncMock,
    )
    def test_delete_subscription_204(
        self, mock_delete: AsyncMock, auth_client
    ) -> None:
        resp = auth_client.delete("/api/v1/news/subscriptions/7")
        assert resp.status_code == 204
        assert mock_delete.await_args.kwargs["subscription_id"] == 7
