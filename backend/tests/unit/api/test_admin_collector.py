"""后台采集任务触发 API 契约测试。"""

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_admin_user, get_db
from app.main import app
from app.schemas.collector import CollectorLogSummaryResponse


@pytest.fixture
def admin_client(client) -> tuple[TestClient, AsyncMock]:
    """返回带管理员鉴权的 client 与 mock 数据库会话。"""
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
class TestAdminCollectorEndpoints:
    @patch("app.api.v1.admin.collector.dispatch_collector_task")
    def test_run_collector_task_dispatches_to_queue(
        self,
        mock_dispatch: AsyncMock,
        admin_client: tuple[TestClient, AsyncMock],
    ) -> None:
        mock_log = MagicMock()
        mock_log.id = 42
        mock_log.celery_task_id = "celery-uuid"
        mock_dispatch.return_value = mock_log
        client, _ = admin_client

        response = client.post(
            "/api/v1/admin/collector/tasks/financial-report/run",
            json={"preferredSource": "cninfo", "symbols": ["000001"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["taskName"] == "financial-report"
        assert data["status"] == "dispatched"
        assert data["logId"] == 42
        assert data["celeryTaskId"] == "celery-uuid"
        mock_dispatch.assert_awaited_once()
        call_kwargs = mock_dispatch.await_args.kwargs
        assert call_kwargs["task_name"] == "financial-report"
        assert call_kwargs["params"]["preferred_source"] == "cninfo"

    @patch("app.api.v1.admin.collector.dispatch_collector_task")
    def test_run_accepts_registry_task_with_trade_date(
        self,
        mock_dispatch: AsyncMock,
        admin_client: tuple[TestClient, AsyncMock],
    ) -> None:
        """注册表内任意任务（含此前未开放的非采集类）均可触发并透传 trade_date。"""
        mock_log = MagicMock()
        mock_log.id = 7
        mock_log.celery_task_id = "review-uuid"
        mock_dispatch.return_value = mock_log
        client, _ = admin_client

        response = client.post(
            "/api/v1/admin/collector/tasks/market-daily-review/run",
            json={"trade_date": "2026-08-28"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["taskName"] == "market-daily-review"
        assert data["logId"] == 7
        call_kwargs = mock_dispatch.await_args.kwargs
        assert call_kwargs["params"] == {"trade_date": "2026-08-28"}

    @patch("app.api.v1.admin.collector.dispatch_collector_task")
    def test_run_unknown_task_returns_404(
        self,
        mock_dispatch: AsyncMock,
        admin_client: tuple[TestClient, AsyncMock],
    ) -> None:
        client, _ = admin_client

        response = client.post("/api/v1/admin/collector/tasks/not-a-task/run")

        assert response.status_code == 404
        mock_dispatch.assert_not_awaited()

    def test_get_collector_task_catalog(
        self,
        admin_client: tuple[TestClient, AsyncMock],
    ) -> None:
        """任务目录由注册表派生：覆盖全部任务且带中文 label。"""
        client, _ = admin_client

        response = client.get("/api/v1/admin/collector/tasks/catalog")

        assert response.status_code == 200
        items = response.json()["items"]
        names = {item["name"] for item in items}
        assert len(items) == 59
        assert "fed-watch" in names
        assert "kb-transcribe" in names
        assert "kb-cleanup" in names
        assert "kb-extract" in names
        assert "kb-vision" in names
        assert "kb-index" in names
        assert "paper-trade-sync" in names
        assert "financial-statement" in names
        assert "stock-shares" in names
        assert "sector-kline" in names
        assert "market-daily-review" in names
        assert "limit-up-ai-review" in names
        assert "sector-anomaly" in names
        assert "stock-anomaly" in names
        assert "news-score" in names
        assert "news-storyline" in names
        assert "news-topic" in names
        assert "news-subscription-match" in names
        assert "stock-daily-analysis" in names
        assert "index-auction" in names
        assert "cls-investkalendar" in names
        assert "chain-refresh" in names
        assert "collector-log-cleanup" in names
        assert "kline-freshness" in names
        assert "trade-calendar-seed" in names
        by_name = {item["name"]: item for item in items}
        assert by_name["market-daily-review"]["label"] == "每日市场复盘"
        assert by_name["kline-freshness"]["label"] == "日K新鲜度自愈"
        assert all(item["description"] for item in items)
        assert by_name["limit-up-pool"]["runParams"] == ["trade_date"]
        assert "internal" in by_name["market-daily-review"]["sources"]

    def test_get_collector_task_channels_unknown_task_returns_404(
        self,
        admin_client: tuple[TestClient, AsyncMock],
    ) -> None:
        client, _ = admin_client

        response = client.get("/api/v1/admin/collector/tasks/not-a-task/channels")

        assert response.status_code == 404

    @patch("app.api.v1.admin.collector.list_channels_for_task")
    @patch("app.api.v1.admin.collector.resolve_channel_for_task")
    def test_get_collector_task_channels(
        self,
        mock_resolve: AsyncMock,
        mock_list: AsyncMock,
        admin_client: tuple[TestClient, AsyncMock],
    ) -> None:
        mock_list.return_value = [
            {"source": "cninfo", "name": "巨潮资讯", "is_enabled": True}
        ]
        resolved = MagicMock()
        resolved.source = "cninfo"
        mock_resolve.return_value = resolved
        client, _ = admin_client

        response = client.get("/api/v1/admin/collector/tasks/financial-report/channels")

        assert response.status_code == 200
        data = response.json()
        assert data["taskName"] == "financial-report"
        assert data["resolvedSource"] == "cninfo"
        assert len(data["channels"]) == 1

    @staticmethod
    def _log_row(**overrides: object) -> SimpleNamespace:
        """构造可通过 CamelModel(from_attributes) 校验的日志行。"""
        base = {
            "id": 1,
            "task_name": "kline",
            "source": "sina",
            "status": "failed",
            "celery_task_id": None,
            "started_at": datetime(2026, 9, 17, 8, 0, tzinfo=timezone.utc),
            "finished_at": datetime(2026, 9, 17, 8, 0, 30, tzinfo=timezone.utc),
            "records_count": 0,
            "error_msg": "boom",
            "meta": None,
        }
        base.update(overrides)
        return SimpleNamespace(**base)

    @patch("app.api.v1.admin.collector.CollectorLogService")
    def test_list_collector_logs_paginated_with_status(
        self,
        mock_service_cls: MagicMock,
        admin_client: tuple[TestClient, AsyncMock],
    ) -> None:
        """logs 列表改分页响应：透传 page/page_size/status，返回 total/items。"""
        service = mock_service_cls.return_value
        service.list_recent = AsyncMock(
            return_value=(2, [self._log_row(id=7, status="failed")])
        )
        client, _ = admin_client

        response = client.get(
            "/api/v1/admin/collector/logs",
            params={
                "page": 1,
                "page_size": 1,
                "status": "failed",
                "start_date": "2026-09-01",
                "end_date": "2026-09-17",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["page"] == 1
        assert data["pageSize"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["taskName"] == "kline"
        assert data["items"][0]["status"] == "failed"
        service.list_recent.assert_awaited_once_with(
            1,
            1,
            task_name=None,
            source=None,
            status="failed",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 17),
        )

    @patch("app.api.v1.admin.collector.CollectorLogService")
    def test_list_collector_logs_invalid_status_returns_400(
        self,
        mock_service_cls: MagicMock,
        admin_client: tuple[TestClient, AsyncMock],
    ) -> None:
        from app.core.exceptions import BadRequestError

        mock_service_cls.return_value.list_recent = AsyncMock(
            side_effect=BadRequestError("status must be one of pending, running, ...")
        )
        client, _ = admin_client

        response = client.get(
            "/api/v1/admin/collector/logs", params={"status": "nope"}
        )

        assert response.status_code == 400

    @patch("app.api.v1.admin.collector.CollectorLogService")
    def test_get_collector_log_summary(
        self,
        mock_service_cls: MagicMock,
        admin_client: tuple[TestClient, AsyncMock],
    ) -> None:
        """今日汇总端点：service 结果原样透传，wire 为 camelCase。"""
        service = mock_service_cls.return_value
        service.get_today_summary = AsyncMock(
            return_value=CollectorLogSummaryResponse(
                date="2026-09-17",
                success_count=182,
                partial_count=1,
                failed_count=3,
                skipped_count=2,
                running_count=1,
                pending_count=0,
            )
        )
        client, _ = admin_client

        response = client.get("/api/v1/admin/collector/logs/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["date"] == "2026-09-17"
        assert data["successCount"] == 182
        assert data["partialCount"] == 1
        assert data["failedCount"] == 3
        assert data["skippedCount"] == 2
        assert data["runningCount"] == 1
        assert data["pendingCount"] == 0
