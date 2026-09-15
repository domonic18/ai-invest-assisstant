"""采集健康监测端点契约测试（鉴权 / camelCase wire / 手动触发与清空）。"""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.core.clock import today_cn
from app.dependencies import get_current_admin_user
from app.main import app


@pytest.fixture
def admin_user():
    return type(
        "User",
        (object,),
        {"id": 1, "username": "admin", "role": "admin", "is_active": True},
    )()


@pytest.fixture
def auth_client(client, admin_user):
    app.dependency_overrides[get_current_admin_user] = lambda: admin_user
    yield client
    app.dependency_overrides.clear()


_NOW = datetime(2026, 9, 16, 0, 30, tzinfo=timezone.utc)


def _overview_payload() -> dict:
    return {
        "health_score": 92,
        "total": 50,
        "counts": {
            "healthy": 44, "degraded": 2, "critical": 1,
            "silent": 1, "paused": 1, "unconfigured": 1,
        },
        "success_rate_24h": 0.95,
        "domains": [
            {"domain": "kline", "total": 7, "healthy": 6,
             "degraded": 1, "critical": 0, "silent": 0},
        ],
        "checked_at": _NOW,
        "stale_after": _NOW + timedelta(hours=48),
    }


@pytest.mark.unit
class TestCollectorHealthEndpoints:
    def test_requires_auth(self, client) -> None:
        resp = client.get("/api/v1/admin/collector/health/overview")
        assert resp.status_code in (401, 403)

    @patch(
        "app.api.v1.admin.collector_health.health_service.get_overview",
        new_callable=AsyncMock,
    )
    def test_overview_wire_shape(self, mock_overview: AsyncMock, auth_client) -> None:
        mock_overview.return_value = _overview_payload()
        resp = auth_client.get("/api/v1/admin/collector/health/overview")

        assert resp.status_code == 200
        data = resp.json()
        assert data["healthScore"] == 92
        assert data["successRate24h"] == 0.95
        assert data["counts"]["critical"] == 1
        assert data["domains"][0]["domain"] == "kline"
        assert data["checkedAt"] == "2026-09-16T00:30:00Z"
        assert data["staleAfter"] == "2026-09-18T00:30:00Z"

    @patch(
        "app.api.v1.admin.collector_health.health_service.get_tasks",
        new_callable=AsyncMock,
    )
    def test_tasks_wire_shape(self, mock_tasks: AsyncMock, auth_client) -> None:
        mock_tasks.return_value = [
            {
                "task_type": "kline", "source": "sina", "status": "healthy",
                "role": "primary", "domain": "kline",
                "success_rate_24h": 1.0, "success_rate_7d": 0.98,
                "consecutive_failures": 0, "windows_without_success": 0,
                "last_success_at": _NOW, "last_error_summary": None,
                "last_error_cause": None, "is_high_frequency": False,
                "last_records_count": 5432, "last_records_date": date(2026, 9, 15),
                "state_changed_at": _NOW, "checked_at": _NOW,
                "schedule": "30 16 * * 1-5", "is_active": True,
            }
        ]
        resp = auth_client.get("/api/v1/admin/collector/health/tasks?domain=kline")

        assert resp.status_code == 200
        item = resp.json()[0]
        assert item["taskType"] == "kline"
        assert item["successRate7d"] == 0.98
        assert item["windowsWithoutSuccess"] == 0
        assert item["isHighFrequency"] is False
        assert item["lastRecordsDate"] == "2026-09-15"
        assert item["isActive"] is True
        mock_tasks.assert_awaited_once()

    @patch(
        "app.api.v1.admin.collector_health.health_service.get_channels",
        new_callable=AsyncMock,
    )
    def test_channels_wire_shape(self, mock_channels: AsyncMock, auth_client) -> None:
        mock_channels.return_value = [
            {
                "source": "eastmoney", "domain_count": 3, "instance_count": 5,
                "success_rate_7d": 0.83, "fault_count": 2,
                "causes": {"waf": 1, "network": 1},
            }
        ]
        resp = auth_client.get("/api/v1/admin/collector/health/channels")

        assert resp.status_code == 200
        item = resp.json()[0]
        assert item["source"] == "eastmoney"
        assert item["domainCount"] == 3
        assert item["successRate7d"] == 0.83
        assert item["faultCount"] == 2
        assert item["causes"] == {"waf": 1, "network": 1}

    @patch(
        "app.api.v1.admin.collector_health.health_service.get_schedule_check",
        new_callable=AsyncMock,
    )
    def test_schedule_check_wire_shape(
        self, mock_schedule: AsyncMock, auth_client
    ) -> None:
        today = today_cn()
        mock_schedule.return_value = {
            "date": today,
            "is_trade_day": True,
            "items": [
                {
                    "task_type": "kline", "source": "sina", "domain": "kline",
                    "role": "primary", "is_active": True, "has_task_row": True,
                    "schedule": "30 16 * * 1-5", "window_total": 1,
                    "success_windows": 1, "skipped_windows": 0,
                    "failed_windows": 0, "missing_windows": 0, "exempted": False,
                    "last_error_summary": None, "last_error_cause": None,
                }
            ],
        }
        resp = auth_client.get(
            f"/api/v1/admin/collector/health/schedule-check?date={today.isoformat()}"
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["date"] == today.isoformat()
        assert data["isTradeDay"] is True
        assert data["items"][0]["windowTotal"] == 1
        assert data["items"][0]["successWindows"] == 1
        assert data["items"][0]["hasTaskRow"] is True

    def test_schedule_check_rejects_future_date(self, auth_client) -> None:
        future = (today_cn() + timedelta(days=1)).isoformat()
        resp = auth_client.get(
            f"/api/v1/admin/collector/health/schedule-check?date={future}"
        )

        assert resp.status_code == 422

    def test_schedule_check_rejects_date_older_than_one_year(self, auth_client) -> None:
        old = (today_cn() - timedelta(days=366)).isoformat()
        resp = auth_client.get(
            f"/api/v1/admin/collector/health/schedule-check?date={old}"
        )

        assert resp.status_code == 422

    @patch(
        "app.api.v1.admin.collector_health.health_service.run_check",
        new_callable=AsyncMock,
    )
    def test_run_check(self, mock_run: AsyncMock, auth_client, mock_session) -> None:
        mock_run.return_value = {
            "checked_at": _NOW,
            "total": 50,
            "failed": 0,
            "orphaned": 2,
            "status_counts": {"healthy": 47, "degraded": 2, "silent": 1},
        }
        resp = auth_client.post("/api/v1/admin/collector/health/run")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 50
        assert data["orphaned"] == 2
        assert data["statusCounts"] == {"healthy": 47, "degraded": 2, "silent": 1}

    @patch(
        "app.api.v1.admin.collector_health.health_service.clear_snapshots",
        new_callable=AsyncMock,
    )
    def test_clear_snapshots(
        self, mock_clear: AsyncMock, auth_client, mock_session
    ) -> None:
        mock_clear.return_value = 48
        resp = auth_client.delete(
            "/api/v1/admin/collector/health/snapshots?task_type=kline"
        )

        assert resp.status_code == 200
        assert resp.json() == {"deleted": 48}
        mock_clear.assert_awaited_once_with(
            mock_session, task_type="kline", source=None
        )
