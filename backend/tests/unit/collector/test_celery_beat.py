"""Celery Beat 数据库调度器契约测试。"""

from unittest.mock import MagicMock, patch

import pytest
from celery.schedules import crontab

from collector.celery_beat import CollectorDatabaseScheduler, _normalize_cron_field


@pytest.mark.unit
class TestNormalizeCronField:
    def test_step_only_normalized(self) -> None:
        assert _normalize_cron_field("0/30") == "*/30"

    def test_range_with_step_unchanged(self) -> None:
        assert _normalize_cron_field("2-57/5") == "2-57/5"

    def test_asterisk_unchanged(self) -> None:
        assert _normalize_cron_field("*") == "*"


@pytest.mark.unit
class TestCollectorDatabaseScheduler:
    def test_load_schedules_from_collector_task(self) -> None:
        rows = [
            {
                "task_name": "quote-daily",
                "task_type": "quote",
                "source": "sina",
                "schedule": "*/5 9-15 * * 1-5",
            },
            {
                "task_name": "financial-report-nightly",
                "task_type": "financial-report",
                "source": "cninfo",
                "schedule": "0 2 * * 1-5",
            },
        ]

        app = MagicMock()
        app.conf.beat_schedule = {}
        with patch.object(
            CollectorDatabaseScheduler,
            "_fetch_active_schedules",
            return_value=rows,
        ):
            scheduler = CollectorDatabaseScheduler(app=app)

        schedule = dict(scheduler.schedule)
        assert "collector-task-quote-daily" in schedule
        assert "collector-task-financial-report-nightly" in schedule

        realtime_entry = schedule["collector-task-quote-daily"]
        assert realtime_entry.task == "collector.celery_tasks.run_collector_task"
        assert isinstance(realtime_entry.schedule, crontab)
        assert realtime_entry.options["queue"] == "collector.realtime"
        payload = realtime_entry.args[0]
        assert payload["task"] == "quote"
        assert payload["task_name"] == "quote-daily"
        assert payload["preferred_source"] == "sina"

        heavy_entry = schedule["collector-task-financial-report-nightly"]
        assert heavy_entry.options["queue"] == "collector.heavy"

    def test_invalid_schedule_is_skipped(self) -> None:
        rows = [
            {
                "task_name": "bad-task",
                "task_type": "quote",
                "source": "sina",
                "schedule": "not-a-cron",
            }
        ]

        app = MagicMock()
        app.conf.beat_schedule = {}
        with patch.object(
            CollectorDatabaseScheduler,
            "_fetch_active_schedules",
            return_value=rows,
        ):
            scheduler = CollectorDatabaseScheduler(app=app)

        assert "collector-task-bad-task" not in scheduler.schedule

    def test_empty_schedule_is_skipped(self) -> None:
        rows = [
            {
                "task_name": "manual-task",
                "task_type": "quote",
                "source": "sina",
                "schedule": None,
            }
        ]

        app = MagicMock()
        app.conf.beat_schedule = {}
        with patch.object(
            CollectorDatabaseScheduler,
            "_fetch_active_schedules",
            return_value=rows,
        ):
            scheduler = CollectorDatabaseScheduler(app=app)

        assert "collector-task-manual-task" not in scheduler.schedule
