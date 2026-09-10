"""渠道监控服务判定矩阵测试（注册表驱动，monitor_type 分派两个判定器）。"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.core.clock import CN_TZ
from app.services.news import news_channel_service
from app.services.news.news_channel_service import (
    MONITOR_STREAM,
    MONITOR_TASK_LOG,
    NEWS_CHANNELS,
    NewsChannel,
    get_channels_status,
    register_channel,
)

FLASH_SCHEDULE = "0/30 * * * *"
REPORT_SCHEDULE = "0 8,18 * * *"


def _at(h_cn: int, m_cn: int = 0) -> datetime:
    """2026-09-08 指定 CN 时刻转 aware UTC。"""
    return datetime(2026, 9, 8, h_cn, m_cn, tzinfo=CN_TZ).astimezone(timezone.utc)


def _run(
    status: str,
    started_at: datetime,
    finished_at: datetime | None = None,
    records: int = 0,
) -> SimpleNamespace:
    return SimpleNamespace(
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        records_count=records,
    )


@contextmanager
def _service_mocks(
    *,
    runs_by_channel: dict[tuple[str, str], list[Any]] | None = None,
    schedules: dict[tuple[str, str], str] | None = None,
    today: tuple[int, datetime | None] = (120, None),
    stats: tuple[int, int, int] = (100, 80, 12),
    heartbeat: int = 1,
) -> Iterator[SimpleNamespace]:
    """patch 判定器的外部依赖：Redis 心跳 / 任务日志 / 任务配置 / 源表统计。

    runs_by_channel / schedules 均以渠道身份 (task_type, source) 为键。
    """
    runs_by_channel = runs_by_channel or {}
    schedules = schedules or {
        ("news", "eastmoney"): FLASH_SCHEDULE,
        ("research-report", "eastmoney"): REPORT_SCHEDULE,
    }
    fake_redis = AsyncMock()
    fake_redis.exists.return_value = heartbeat
    today_mock = AsyncMock(return_value=today)
    stats_mock = AsyncMock(return_value=stats)
    with (
        patch(
            "app.services.news.news_channel_service.get_redis",
            return_value=fake_redis,
        ),
        patch(
            "app.services.news.news_channel_service.CollectorLogRepository"
        ) as log_cls,
        patch(
            "app.services.news.news_channel_service.CollectorTaskRepository"
        ) as task_cls,
        patch(
            "app.services.news.news_channel_service.telegraph_repository.today_overview",
            today_mock,
        ),
        patch(
            "app.services.news.news_channel_service.ai_score_repository.today_stats",
            stats_mock,
        ),
    ):
        log_cls.return_value.list_runs_for_task = AsyncMock(
            side_effect=lambda task_name, since, source=None, limit=500: runs_by_channel.get(
                (task_name, source), []
            )
        )
        task_cls.return_value.get_by_type_and_source = AsyncMock(
            side_effect=lambda task_type, source: SimpleNamespace(
                schedule=schedules.get((task_type, source))
            )
        )
        yield SimpleNamespace(redis=fake_redis, today=today_mock, stats=stats_mock)


def _channel_of(result: Any, key: str) -> Any:
    return next(ch for ch in result.channels if ch.key == key)


async def _status(now: datetime, **kwargs: Any) -> Any:
    with _service_mocks(**kwargs):
        return await get_channels_status(None, now=now)  # type: ignore[arg-type]


@pytest.mark.unit
class TestStreamChannel:
    async def test_live_with_counts(self) -> None:
        last_at = _at(11, 55)
        with _service_mocks(today=(120, last_at)) as mocks:
            result = await get_channels_status(None, now=_at(12))  # type: ignore[arg-type]
        ch = _channel_of(result, "cls_telegraph")
        assert ch.status == "live"
        assert ch.status_text == "LIVE 采集中"
        assert ch.today_count == 120
        assert ch.last_updated_at == last_at
        assert ch.lag_seconds == 300
        assert (
            mocks.redis.exists.await_args.args[0]
            == "collector:stream:cls_telegraph:heartbeat"
        )

    async def test_heartbeat_missing_delayed(self) -> None:
        result = await _status(_at(12), heartbeat=0)
        ch = _channel_of(result, "cls_telegraph")
        assert ch.status == "delayed"
        assert ch.status_text == "采集延迟"


@pytest.mark.unit
class TestTaskLogPolling:
    async def test_recent_success_ok(self) -> None:
        runs = [_run("success", _at(11, 30), _at(11, 32), records=12)]
        result = await _status(_at(12), runs_by_channel={("news", "eastmoney"): runs})
        ch = _channel_of(result, "eastmoney_flash_news")
        assert ch.status == "ok"
        assert ch.status_text == "正常运行"
        assert ch.today_count == 12
        assert ch.last_updated_at == _at(11, 32)

    async def test_stale_success_delayed(self) -> None:
        # 最近成功停留在 10:58（覆盖 10:30 轮），12:10 仍无新成功 -> 超两轮窗口
        runs = [_run("success", _at(10, 30), _at(10, 58))]
        result = await _status(_at(12, 10), runs_by_channel={("news", "eastmoney"): runs})
        assert _channel_of(result, "eastmoney_flash_news").status == "delayed"

    async def test_no_runs_early_morning_ok(self) -> None:
        # 跨日后 10 分钟，首轮（00:00）还没跑完 -> 正常等待
        result = await _status(_at(0, 10), runs_by_channel={("news", "eastmoney"): []})
        assert _channel_of(result, "eastmoney_flash_news").status == "ok"

    async def test_no_runs_beyond_window_delayed(self) -> None:
        # 当日从 00:00 起一轮未成功，超过两轮窗口 -> delayed
        result = await _status(_at(1, 10), runs_by_channel={("news", "eastmoney"): []})
        assert _channel_of(result, "eastmoney_flash_news").status == "delayed"

    async def test_running_latest_terminal_falls_back_to_success(self) -> None:
        # 最新 run 在跑不算终态；今日最近成功仍覆盖节奏 -> ok
        runs = [
            _run("running", _at(11, 59)),
            _run("success", _at(11, 30), _at(11, 32), records=5),
        ]
        result = await _status(_at(12), runs_by_channel={("news", "eastmoney"): runs})
        ch = _channel_of(result, "eastmoney_flash_news")
        assert ch.status == "ok"
        assert ch.last_updated_at == _at(11, 32)

    async def test_only_failed_runs_delayed(self) -> None:
        runs = [_run("failed", _at(11, 31), _at(11, 31))]
        result = await _status(_at(11, 40), runs_by_channel={("news", "eastmoney"): runs})
        ch = _channel_of(result, "eastmoney_flash_news")
        assert ch.status == "delayed"
        assert ch.today_count == 0
        assert ch.last_updated_at == _at(11, 31)


@pytest.mark.unit
class TestTaskLogBatch:
    async def test_today_success_batch(self) -> None:
        runs = [_run("success", _at(18), _at(18, 5), records=40)]
        result = await _status(
            _at(23), runs_by_channel={("research-report", "eastmoney"): runs}
        )
        ch = _channel_of(result, "eastmoney_research_report")
        assert ch.status == "batch"
        assert ch.status_text == "每日批次"
        assert ch.today_count == 40

    async def test_morning_wait_before_grace(self) -> None:
        # 8:00 批次过后 1 小时无成功，仍在宽限窗口 -> 正常等待
        result = await _status(_at(9), runs_by_channel={("research-report", "eastmoney"): []})
        assert _channel_of(result, "eastmoney_research_report").status == "batch"

    async def test_overdue_no_success_delayed(self) -> None:
        # 8:00 批次过后 2.5 小时仍无成功 -> delayed
        result = await _status(
            _at(10, 30), runs_by_channel={("research-report", "eastmoney"): []}
        )
        assert _channel_of(result, "eastmoney_research_report").status == "delayed"


@pytest.mark.unit
class TestStatsAndRegistry:
    async def test_stats_fields(self) -> None:
        result = await _status(_at(12), stats=(100, 80, 12))
        assert result.stats.today_total == 100
        assert result.stats.scored_count == 80
        assert result.stats.high_count == 12

    async def test_day_start_uses_cn_boundary(self) -> None:
        with _service_mocks(stats=(0, 0, 0)) as mocks:
            await get_channels_status(None, now=_at(12))  # type: ignore[arg-type]
        assert mocks.stats.await_args.kwargs["day_start"] == datetime(
            2026, 9, 7, 16, tzinfo=timezone.utc
        )

    async def test_default_registry_three_channels(self) -> None:
        result = await _status(_at(12))
        assert [ch.key for ch in result.channels] == [
            "cls_telegraph",
            "eastmoney_flash_news",
            "eastmoney_research_report",
        ]

    async def test_fake_channel_registered_appears(self) -> None:
        fake = NewsChannel(
            key="x_video",
            name="X 博主",
            monitor_type=MONITOR_STREAM,
            poll_desc="5 分钟轮询",
            heartbeat_key="collector:stream:x_video:heartbeat",
        )
        register_channel(fake)
        try:
            result = await _status(_at(12), today=(120, _at(11, 55)))
        finally:
            NEWS_CHANNELS.remove(fake)
        ch = _channel_of(result, "x_video")
        assert ch.status == "live"
        assert ch.today_count == 0  # 未声明 today_query -> 空计数
        assert ch.last_updated_at is None
        assert ch.lag_seconds is None

    def test_module_exports_register(self) -> None:
        assert callable(news_channel_service.register_channel)


@pytest.mark.unit
class TestRegistryConsistency:
    """钉死监控注册表与采集运行时的键空间契约：新渠道键写错直接红灯。"""

    def test_task_log_channels_match_runtime_registry(self) -> None:
        from collector.runtime.registry import TASK_SPECS

        task_log_channels = [
            ch for ch in NEWS_CHANNELS if ch.monitor_type == MONITOR_TASK_LOG
        ]
        assert task_log_channels, "注册表至少应有一条 task-log 渠道"
        for ch in task_log_channels:
            assert ch.task_type in TASK_SPECS, (
                f"{ch.key}: task_type={ch.task_type} 不在 TASK_SPECS"
            )
            spec = TASK_SPECS[ch.task_type]
            assert ch.source in spec.collectors, (
                f"{ch.key}: source={ch.source} 不在 {ch.task_type} 的 collectors"
            )
