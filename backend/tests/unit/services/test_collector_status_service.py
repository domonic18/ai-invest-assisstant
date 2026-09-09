"""采集引擎状态服务单测：运行中/最近运行/未来 12 小时计划展开。"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.clock import CN_TZ
from app.services.workbench import collector_status_service

_MODULE = "app.services.workbench.collector_status_service"

_NOW = datetime(2026, 9, 4, 15, 0, tzinfo=CN_TZ)  # 周五 15:00


def _log_row(
    *,
    task_name: str,
    status: str,
    started_min_ago: float,
    duration_s: int | None = 30,
    records: int = 10,
    source: str = "sina",
) -> MagicMock:
    started = (_NOW - timedelta(minutes=started_min_ago)).astimezone(timezone.utc)
    row = MagicMock()
    row.task_name = task_name
    row.status = status
    row.started_at = started
    row.finished_at = (
        started + timedelta(seconds=duration_s) if duration_s is not None else None
    )
    row.records_count = records
    row.source = source
    return row


def _task(
    *,
    task_name: str,
    task_type: str,
    schedule: str,
    source: str = "sina",
) -> MagicMock:
    task = MagicMock()
    task.task_name = task_name
    task.task_type = task_type
    task.schedule = schedule
    task.source = source
    task.is_active = True
    return task


async def _run_service(
    *,
    running: MagicMock | None = None,
    recent: list[MagicMock] | None = None,
    tasks: list[MagicMock] | None = None,
):
    with (
        patch(
            f"{_MODULE}.CollectorLogRepository",
            MagicMock(
                return_value=MagicMock(
                    get_latest_running=AsyncMock(return_value=running),
                    list_recent_terminal=AsyncMock(return_value=recent or []),
                )
            ),
        ),
        patch(
            f"{_MODULE}.CollectorTaskRepository",
            MagicMock(
                return_value=MagicMock(
                    list_active_scheduled=AsyncMock(return_value=tasks or [])
                )
            ),
        ),
    ):
        return await collector_status_service.get_collector_status(AsyncMock(), now=_NOW)


@pytest.mark.unit
class TestGetCollectorStatus:
    @pytest.mark.asyncio
    async def test_idle_without_running_row(self) -> None:
        result = await _run_service(running=None)

        assert result.is_running is False
        assert result.running is None

    @pytest.mark.asyncio
    async def test_running_row_mapped_with_label(self) -> None:
        row = _log_row(
            task_name="market-breadth", status="running", started_min_ago=0.8, duration_s=None
        )
        result = await _run_service(running=row)

        assert result.is_running is True
        assert result.running is not None
        assert result.running.task_label != "market-breadth"  # 命中 registry 中文 label
        assert result.running.duration_seconds is None

    @pytest.mark.asyncio
    async def test_recent_runs_duration_and_records(self) -> None:
        rows = [
            _log_row(task_name="market-breadth", status="success", started_min_ago=3, records=1240),
            _log_row(task_name="market-amount", status="skipped", started_min_ago=10),
        ]
        result = await _run_service(recent=rows)

        assert [r.task_name for r in result.recent_runs] == [
            "market-breadth",
            "market-amount",
        ]
        assert result.recent_runs[0].duration_seconds == 30
        assert result.recent_runs[0].records_count == 1240

    @pytest.mark.asyncio
    async def test_upcoming_expands_multi_time_cron_within_window(self) -> None:
        tasks = [
            _task(
                task_name="eastmoney_a50_kline",
                task_type="a50-kline",
                schedule="40 17,21 * * 1-5",
                source="eastmoney",
            ),
        ]
        result = await _run_service(tasks=tasks)

        times = [item.run_at.astimezone(CN_TZ).strftime("%H:%M") for item in result.upcoming]
        assert times == ["17:40", "21:40"]
        assert result.upcoming[0].task_name == "eastmoney_a50_kline"
        assert result.upcoming[0].source == "eastmoney"

    @pytest.mark.asyncio
    async def test_upcoming_beyond_window_excluded_and_sorted(self) -> None:
        tasks = [
            _task(task_name="chain_refresh_weekly", task_type="chain-refresh",
                  schedule="0 6 * * 6", source="internal"),  # 周六 06:00 > 12h 外
            _task(task_name="a", task_type="news", schedule="0 16 * * 1-5"),
            _task(task_name="b", task_type="etf-kline", schedule="5 16 * * 1-5"),
        ]
        result = await _run_service(tasks=tasks)

        names = [item.task_name for item in result.upcoming]
        assert "chain_refresh_weekly" not in names
        assert names == ["a", "b"]

    @pytest.mark.asyncio
    async def test_invalid_schedule_skipped(self) -> None:
        tasks = [_task(task_name="bad", task_type="kline", schedule="not a cron")]
        result = await _run_service(tasks=tasks)

        assert result.upcoming == []
