"""系统状态扩展端点契约测试：celery-queues 鉴权 / camelCase wire / 服务打桩。"""

from unittest.mock import AsyncMock, patch

import pytest

from app.dependencies import get_current_admin_user
from app.main import app


@pytest.fixture
def admin_client(client):
    """绕过管理员认证的客户端（服务层在用例内打桩）。"""
    from types import SimpleNamespace

    app.dependency_overrides[get_current_admin_user] = lambda: SimpleNamespace(
        id=1, role="admin"
    )
    yield client
    app.dependency_overrides.pop(get_current_admin_user, None)


def _overview() -> dict:
    return {
        "broker_ok": True,
        "queues": [
            {
                "name": "collector.realtime",
                "label": "实时队列",
                "pending_total": 2,
                "tasks": [
                    {
                        "key": "log-1",
                        "task_type": "stock-minute",
                        "label": "股票分钟线",
                        "state": "running",
                        "source": "sina",
                        "started_at": "2026-09-24T07:55:00+00:00",
                        "finished_at": None,
                        "duration_ms": None,
                        "detail": None,
                    },
                    {
                        "key": "pending-0-cid1",
                        "task_type": "stock-minute",
                        "label": "股票分钟线",
                        "state": "pending",
                        "source": "sina",
                        "started_at": None,
                        "finished_at": None,
                        "duration_ms": None,
                        "detail": None,
                    },
                ],
            },
            {
                "name": "collector.batch",
                "label": "批量队列",
                "pending_total": 0,
                "tasks": [
                    {
                        "key": "log-2",
                        "task_type": "market-daily-review",
                        "label": "大盘每日复盘",
                        "state": "failed",
                        "source": "internal",
                        "started_at": "2026-09-24T07:30:00+00:00",
                        "finished_at": "2026-09-24T07:31:00+00:00",
                        "duration_ms": 60000,
                        "detail": "boom",
                    }
                ],
            },
            {"name": "collector.heavy", "label": "重载队列", "pending_total": 0, "tasks": []},
        ],
        "checked_at": "2026-09-24T08:00:00+00:00",
    }


@pytest.mark.unit
class TestCeleryQueuesApi:
    def test_requires_auth(self, client) -> None:
        assert client.get("/api/v1/admin/system/celery-queues").status_code in (401, 403)

    def test_non_admin_forbidden(self, user_client) -> None:
        resp = user_client.get("/api/v1/admin/system/celery-queues")
        assert resp.status_code == 403

    def test_returns_camel_case_wire(self, admin_client) -> None:
        with patch(
            "app.services.admin.celery_queue_service.CeleryQueueService.get_overview",
            AsyncMock(return_value=_overview()),
        ):
            resp = admin_client.get("/api/v1/admin/system/celery-queues")

        assert resp.status_code == 200
        body = resp.json()
        assert body["brokerOk"] is True
        realtime = body["queues"][0]
        assert realtime["label"] == "实时队列"
        assert realtime["pendingTotal"] == 2
        assert realtime["tasks"][0]["taskType"] == "stock-minute"
        assert realtime["tasks"][0]["startedAt"] == "2026-09-24T07:55:00Z"
        failed = body["queues"][1]["tasks"][0]
        assert failed["durationMs"] == 60000
        assert failed["detail"] == "boom"
