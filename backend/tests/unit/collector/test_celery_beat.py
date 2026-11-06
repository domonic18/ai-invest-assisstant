"""Celery Beat 数据库调度器契约测试。"""

from datetime import datetime, timezone
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
        # 定时消息必须携带软/硬时限（与 dispatcher 同源），否则 beat 派发裸奔
        assert realtime_entry.options["soft_time_limit"] > 0
        assert realtime_entry.options["time_limit"] > 0
        payload = realtime_entry.args[0]
        assert payload["task"] == "quote"
        assert payload["task_name"] == "quote-daily"
        assert payload["preferred_source"] == "sina"

        heavy_entry = schedule["collector-task-financial-report-nightly"]
        assert heavy_entry.options["queue"] == "collector.heavy"
        assert heavy_entry.options["soft_time_limit"] > 0
        assert heavy_entry.options["time_limit"] > 0

    def test_sync_reuses_persistent_loop(self) -> None:
        """重复 sync 必须复用同一事件循环，避免 asyncpg 连接跨循环复用崩溃。"""
        app = MagicMock()
        app.conf.beat_schedule = {}
        with patch.object(
            CollectorDatabaseScheduler,
            "_fetch_active_schedules",
            return_value=[],
        ):
            scheduler = CollectorDatabaseScheduler(app=app)
            first = CollectorDatabaseScheduler._ensure_loop()
            scheduler.sync()
            second = CollectorDatabaseScheduler._ensure_loop()

        assert first is second
        assert not first.is_closed()

        first.close()
        CollectorDatabaseScheduler._loop = None

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


@pytest.mark.unit
class TestScheduleEntryRunState:
    """重建条目必须保留运行态，否则定时槽位会被静默跳过。

    celery 的 sync 落点常落在槽位分钟内，而 crontab 判定 `last_run_at`
    落在 `[槽位分钟, +1min)` 时该槽位尚未到期——重建条目等于把槽位推到次日
    （2026-11-06 生产 19:30 槽位 8 个任务全部未派发）。
    """

    _ROWS = [
        {
            "task_name": "plan-1900",
            "task_type": "agent-daily-plan",
            "source": "internal",
            "schedule": "30 19 * * 1-5",
        }
    ]

    @staticmethod
    def _scheduler(rows: list[dict]) -> CollectorDatabaseScheduler:
        app = MagicMock()
        app.conf.beat_schedule = {}
        with patch.object(
            CollectorDatabaseScheduler,
            "_fetch_active_schedules",
            return_value=rows,
        ):
            return CollectorDatabaseScheduler(app=app)

    @staticmethod
    def _sync(scheduler: CollectorDatabaseScheduler, rows: list[dict]) -> None:
        with patch.object(
            CollectorDatabaseScheduler,
            "_fetch_active_schedules",
            return_value=rows,
        ):
            scheduler.sync()

    def test_reload_preserves_last_run_at(self) -> None:
        scheduler = self._scheduler(self._ROWS)
        entry = scheduler.schedule["collector-task-plan-1900"]
        entry.last_run_at = datetime(2026, 11, 5, 19, 30, tzinfo=timezone.utc)

        self._sync(scheduler, self._ROWS)

        reloaded = scheduler.schedule["collector-task-plan-1900"]
        assert reloaded.last_run_at == datetime(2026, 11, 5, 19, 30, tzinfo=timezone.utc)

    def test_reload_preserves_due_state_at_slot(self) -> None:
        """沿用运行态后，槽位时刻仍判定为到期。"""
        scheduler = self._scheduler(self._ROWS)
        entry = scheduler.schedule["collector-task-plan-1900"]
        entry.last_run_at = datetime(2026, 11, 5, 19, 30, tzinfo=timezone.utc)

        self._sync(scheduler, self._ROWS)

        reloaded = scheduler.schedule["collector-task-plan-1900"]
        slot = datetime(2026, 11, 6, 19, 30, tzinfo=timezone.utc)
        reloaded.schedule.now = lambda: slot
        due, _rem = reloaded.schedule.is_due(reloaded.last_run_at)
        assert due is True

    def test_schedule_change_resets_last_run_at(self) -> None:
        """cron 变更等于新调度语义，运行态必须重置。"""
        scheduler = self._scheduler(self._ROWS)
        entry = scheduler.schedule["collector-task-plan-1900"]
        entry.last_run_at = datetime(2026, 11, 5, 19, 30, tzinfo=timezone.utc)

        self._sync(scheduler, [{**self._ROWS[0], "schedule": "0 20 * * 1-5"}])

        reloaded = scheduler.schedule["collector-task-plan-1900"]
        assert reloaded.last_run_at != datetime(2026, 11, 5, 19, 30, tzinfo=timezone.utc)

    def test_crontab_skips_slot_when_last_run_at_inside_slot_minute(self) -> None:
        """回归基线：last_run_at 落在槽位分钟内 → 该槽位判定未到期。"""
        schedule = crontab(minute="30", hour="19", day_of_week="1-5")
        slot = datetime(2026, 11, 6, 19, 30, tzinfo=timezone.utc)
        schedule.now = lambda: slot

        due, _rem = schedule.is_due(datetime(2026, 11, 6, 19, 30, 1, tzinfo=timezone.utc))
        assert due is False

        due, _rem = schedule.is_due(datetime(2026, 11, 5, 19, 30, tzinfo=timezone.utc))
        assert due is True
