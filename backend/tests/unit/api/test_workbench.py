"""工作台聚合端点契约测试（鉴权 / 聚合 shape）。"""

from unittest.mock import AsyncMock, patch

import pytest

from app.dependencies import get_current_user
from app.main import app


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
class TestWorkbenchEndpoint:
    def test_requires_auth(self, client) -> None:
        resp = client.get("/api/v1/workbench")
        assert resp.status_code in (401, 403)

    def test_returns_aggregated_modules(self, auth_client) -> None:
        payload = {
            "calendar": [
                {
                    "id": 1,
                    "event_time": "2026-09-10T02:00:00",
                    "end_time": None,
                    "title": "FOMC 议息会议",
                    "category": "央行",
                    "impact_markets": None,
                    "source": None,
                    "source_url": None,
                    "related_symbols": None,
                }
            ],
            "review": None,
            "telegraph": [],
            "watchlist_groups": [
                {
                    "id": 1,
                    "name": "核心持仓",
                    "is_default": False,
                    "ai_review_enabled": True,
                    "items": [
                        {
                            "code": "600967",
                            "name": "内蒙一机",
                            "trend": [1.0, 2.0],
                            "ai_status": "ready",
                            "ai_summary": "企稳上行",
                        }
                    ],
                }
            ],
            "indices": [],
            "stats": None,
            "global_indices": [
                {"index_code": "GC00Y", "index_name": "COMEX黄金"}
            ],
        }
        with patch(
            "app.api.v1.workbench.workbench_service.get_workbench",
            AsyncMock(return_value=payload),
        ) as svc_mock:
            resp = auth_client.get("/api/v1/workbench")

        assert resp.status_code == 200
        body = resp.json()
        assert body["calendar"][0]["title"] == "FOMC 议息会议"
        assert body["review"] is None
        assert body["watchlist_groups"][0]["items"][0]["code"] == "600967"
        assert body["watchlist_groups"][0]["items"][0]["ai_status"] == "ready"
        assert body["global_indices"][0]["index_name"] == "COMEX黄金"
        args, _kwargs = svc_mock.await_args
        assert args[1] == 3
