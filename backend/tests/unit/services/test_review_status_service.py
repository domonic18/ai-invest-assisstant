"""复盘状态服务单测：日聚合/连击/月成功率/计划时间（固定 now，避免时区漂移）。"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.clock import CN_TZ
from app.services.workbench import review_status_service

_MODULE = "app.services.workbench.review_status_service"

_NOW = datetime(2026, 9, 4, 17, 0, tzinfo=CN_TZ)  # 周五 17:00，当日 16:30 批次已过


def _run(
    *,
    started_cn: datetime,
    status: str,
    duration_s: int = 120,
) -> MagicMock:
    started = started_cn.astimezone(timezone.utc)
    row = MagicMock()
    row.status = status
    row.started_at = started
    row.finished_at = started + timedelta(seconds=duration_s)
    row.records_count = 1
    row.task_name = "market-daily-review"
    row.source = "internal"
    return row


def _task(schedule: str | None = "30 16 * * 1-5") -> MagicMock:
    task = MagicMock()
    task.task_type = "market-daily-review"
    task.task_name = "market_daily_review_1600"
    task.schedule = schedule
    task.source = "internal"
    task.is_active = True
    return task


@pytest.mark.unit
class TestGetReviewStatus:
    async def _run_service(self, runs: list[MagicMock], tasks: list[MagicMock]):
        with (
            patch(
                f"{_MODULE}.CollectorLogRepository",
                MagicMock(return_value=MagicMock(list_runs_for_task=AsyncMock(return_value=runs))),
            ),
            patch(
                f"{_MODULE}.CollectorTaskRepository",
                MagicMock(
                    return_value=MagicMock(
                        list_active_scheduled=AsyncMock(return_value=tasks)
                    )
                ),
            ),
        ):
            return await review_status_service.get_review_status(AsyncMock(), now=_NOW)

    @pytest.mark.asyncio
    async def test_done_with_duration_and_planned_time(self) -> None:
        today_run = _run(
            started_cn=datetime(2026, 9, 4, 16, 32, tzinfo=CN_TZ),
            status="success",
        )
        result = await self._run_service([today_run], [_task()])

        assert result.status == "done"
        assert result.generated_at is not None
        assert result.duration_seconds == 120
        assert result.planned_time == "16:30"
        assert result.next_run_at == datetime(2026, 9, 7, 8, 30, tzinfo=timezone.utc)
        assert result.streak_days == 1
        assert result.month_success_rate == 100.0
        assert result.recent_days[0].trade_date.isoformat() == "2026-09-04"
        assert result.recent_days[0].status == "success"

    @pytest.mark.asyncio
    async def test_pending_before_run_with_today_in_strip(self) -> None:
        yesterday = _run(
            started_cn=datetime(2026, 9, 3, 16, 31, tzinfo=CN_TZ), status="success"
        )
        result = await self._run_service([yesterday], [_task()])

        assert result.status == "pending"
        assert result.generated_at is None
        assert result.recent_days[0].trade_date.isoformat() == "2026-09-04"
        assert result.recent_days[0].status == "pending"
        assert result.recent_days[1].status == "success"

    @pytest.mark.asyncio
    async def test_failed_day_marks_status(self) -> None:
        failed_today = _run(
            started_cn=datetime(2026, 9, 4, 16, 32, tzinfo=CN_TZ), status="failed"
        )
        result = await self._run_service([failed_today], [_task()])

        assert result.status == "failed"
        assert result.generated_at is None
        assert result.month_success_rate == 0.0

    @pytest.mark.asyncio
    async def test_streak_breaks_on_failure_skips_weekend_gap(self) -> None:
        runs = [
            _run(started_cn=datetime(2026, 9, 4, 16, 32, tzinfo=CN_TZ), status="success"),
            _run(started_cn=datetime(2026, 9, 3, 16, 31, tzinfo=CN_TZ), status="success"),
            _run(started_cn=datetime(2026, 9, 2, 16, 31, tzinfo=CN_TZ), status="success"),
            _run(started_cn=datetime(2026, 9, 1, 16, 31, tzinfo=CN_TZ), status="failed"),
            _run(started_cn=datetime(2026, 8, 31, 16, 31, tzinfo=CN_TZ), status="success"),
        ]
        result = await self._run_service(runs, [_task()])

        assert result.streak_days == 3
        assert [d.status for d in result.recent_days] == [
            "success",
            "success",
            "success",
            "failed",
            "success",
        ]

    @pytest.mark.asyncio
    async def test_invalid_schedule_yields_no_plan(self) -> None:
        result = await self._run_service([], [_task(schedule="not a cron")])

        assert result.status == "pending"
        assert result.planned_time is None
        assert result.next_run_at is None
