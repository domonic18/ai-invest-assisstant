"""资讯渠道监控服务：声明式注册表驱动，新渠道登记一行即上监控卡。

判定器按 monitor_type 分派：
- stream-heartbeat：驻留进程 Redis 心跳（EXISTS 即 live）
- task-log：collector_task 的 cron + collector_log 当日运行记录；
  轮询型两轮触发间隔内无成功即 delayed，每日批次型当日首个计划
  时刻超宽限仍无成功即 delayed

键空间契约：collector_log.task_name 存 TASK_SPECS 键（task_type），
渠道身份 = (task_type, source)，与采集运行时（resolver/TaskSpec.collectors）
同一键空间；task-log 条目据此查询，禁止用 collector_task.task_name
实例名查 collector_log。一致性由 test_news_channel_service 钉死。
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone

import structlog
from croniter import croniter
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis
from app.core.clock import CN_TZ, now_cn
from app.core.constants import (
    NEWS_SOURCE_TELEGRAPH,
    STREAM_HEARTBEAT_KEY_TEMPLATE,
)
from app.models.collector_log import CollectorLog
from app.repositories.admin.collector_log_repository import CollectorLogRepository
from app.repositories.admin.collector_task_repository import CollectorTaskRepository
from app.repositories.market import telegraph_repository
from app.repositories.news import ai_score_repository
from app.schemas.news import (
    NewsChannelResponse,
    NewsChannelsResponse,
    NewsChannelStatus,
    NewsStatsResponse,
)

logger = structlog.get_logger(__name__)

MONITOR_STREAM = "stream-heartbeat"
MONITOR_TASK_LOG = "task-log"

# 批次型渠道当日首个计划时刻过后仍无成功的宽限
_BATCH_GRACE = timedelta(hours=2)
# cron 缺失/非法时轮询型按 30 分钟节奏判定
_POLL_FALLBACK_INTERVAL = timedelta(minutes=30)

TodayQuery = Callable[[AsyncSession, datetime], Awaitable[tuple[int, datetime | None]]]

_STATUS_TEXT: dict[NewsChannelStatus, str] = {
    "live": "LIVE 采集中",
    "ok": "正常运行",
    "delayed": "采集延迟",
    "batch": "每日批次",
}


@dataclass(frozen=True)
class NewsChannel:
    """渠道监控声明：monitor_type 决定判定器，其余为展示与查询参数。

    task-log 型按渠道身份 (task_type, source) 查询运行记录与计划。
    """

    key: str
    name: str
    monitor_type: str
    poll_desc: str
    heartbeat_key: str | None = None
    task_type: str | None = None
    source: str | None = None
    batch_schedule: bool = False
    today_query: TodayQuery | None = None


async def _telegraph_today(
    session: AsyncSession, day_start: datetime
) -> tuple[int, datetime | None]:
    return await telegraph_repository.today_overview(session, day_start=day_start)


# 渠道注册表：新渠道在此登记一行即纳入监控（不存在的渠道不登记，不模拟数据）
NEWS_CHANNELS: list[NewsChannel] = [
    NewsChannel(
        key=NEWS_SOURCE_TELEGRAPH,
        name="财联社电报",
        monitor_type=MONITOR_STREAM,
        poll_desc="10s 增量轮询 · 驻留进程",
        heartbeat_key=STREAM_HEARTBEAT_KEY_TEMPLATE.format(
            source=NEWS_SOURCE_TELEGRAPH
        ),
        today_query=_telegraph_today,
    ),
    NewsChannel(
        key="eastmoney_flash_news",
        name="东财快讯",
        monitor_type=MONITOR_TASK_LOG,
        poll_desc="30 分钟轮询",
        task_type="news",
        source="eastmoney",
    ),
    NewsChannel(
        key="eastmoney_research_report",
        name="东财研报",
        monitor_type=MONITOR_TASK_LOG,
        poll_desc="每日 2 次（8:00 / 18:00）",
        task_type="research-report",
        source="eastmoney",
        batch_schedule=True,
    ),
]


def register_channel(channel: NewsChannel) -> None:
    """登记渠道（渠道扩展用；初始注册表静态声明）。"""
    NEWS_CHANNELS.append(channel)


def _day_start(now: datetime) -> datetime:
    """now 所在 CN 日历日的 00:00，转 aware UTC。"""
    return datetime.combine(now.astimezone(CN_TZ).date(), time.min, CN_TZ).astimezone(
        timezone.utc
    )


def _lag_seconds(now: datetime, last_at: datetime | None) -> int | None:
    if last_at is None:
        return None
    return max(0, int((now - last_at).total_seconds()))


def _expand_cron(schedule: str, base: datetime) -> list[datetime]:
    """从 base 起展开连续 4 个触发时刻（naive CN 时间）；非法返回空。"""
    try:
        it = croniter(schedule, base)
        return [it.get_next(datetime) for _ in range(4)]
    except Exception:
        return []


def _day_base(day_start: datetime) -> datetime:
    """CN 日界回拨 1 秒作 cron 展开基点（纳入恰落在 00:00 的触发点）。"""
    return day_start.astimezone(CN_TZ).replace(tzinfo=None) - timedelta(seconds=1)


def _cron_interval(schedule: str | None, day_start: datetime) -> timedelta:
    """cron 相邻触发的最大间隔（轮询型 delayed 阈值用）。"""
    if not schedule:
        return _POLL_FALLBACK_INTERVAL
    times = _expand_cron(schedule, _day_base(day_start))
    if len(times) < 2:
        return _POLL_FALLBACK_INTERVAL
    gaps = [b - a for a, b in zip(times, times[1:])]
    return max(gaps)


def _first_trigger_today(
    schedule: str | None, day_start: datetime, now: datetime
) -> datetime | None:
    """CN 日界内第一个 <= now 的计划触发时刻（aware UTC）。"""
    if not schedule:
        return None
    times = _expand_cron(schedule, _day_base(day_start))
    if not times:
        return None
    first = times[0]
    if first > now.astimezone(CN_TZ).replace(tzinfo=None):
        return None
    return first.replace(tzinfo=CN_TZ).astimezone(timezone.utc)


def _success_at(run: CollectorLog) -> datetime | None:
    return run.finished_at or run.started_at


def _task_log_status(
    channel: NewsChannel,
    schedule: str | None,
    success_run: CollectorLog | None,
    now: datetime,
    day_start: datetime,
) -> NewsChannelStatus:
    """task-log 渠道健康判定：当日最近成功 run 是否还在节奏窗口内。"""
    if channel.batch_schedule:
        if success_run is not None:
            return "batch"
        first = _first_trigger_today(schedule, day_start, now)
        if first is not None and now - first > _BATCH_GRACE:
            return "delayed"
        return "batch"
    threshold = _cron_interval(schedule, day_start) * 2
    last_ok = _success_at(success_run) if success_run is not None else None
    if last_ok is not None:
        return "delayed" if now - last_ok > threshold else "ok"
    first = _first_trigger_today(schedule, day_start, now)
    if first is not None and now - first > threshold:
        return "delayed"
    return "ok"


async def _status_stream(
    channel: NewsChannel,
    session: AsyncSession,
    now: datetime,
    day_start: datetime,
) -> NewsChannelResponse:
    alive = bool(await get_redis().exists(channel.heartbeat_key or ""))
    count, last_at = (
        await channel.today_query(session, day_start)
        if channel.today_query is not None
        else (0, None)
    )
    status: NewsChannelStatus = "live" if alive else "delayed"
    return NewsChannelResponse(
        key=channel.key,
        name=channel.name,
        status=status,
        status_text=_STATUS_TEXT[status],
        poll_desc=channel.poll_desc,
        today_count=count,
        last_updated_at=last_at,
        lag_seconds=_lag_seconds(now, last_at),
    )


async def _status_task_log(
    channel: NewsChannel,
    session: AsyncSession,
    now: datetime,
    day_start: datetime,
    task_repo: CollectorTaskRepository,
) -> NewsChannelResponse:
    log_repo = CollectorLogRepository(session)
    task = await task_repo.get_by_type_and_source(
        channel.task_type or "", channel.source or ""
    )
    runs = await log_repo.list_runs_for_task(
        channel.task_type or "", source=channel.source, since=day_start
    )
    latest_terminal = next((r for r in runs if r.status != "running"), None)
    success_run = next((r for r in runs if r.status == "success"), None)
    today_count = sum(r.records_count or 0 for r in runs)
    last_at = (
        (latest_terminal.finished_at or latest_terminal.started_at)
        if latest_terminal is not None
        else None
    )
    status = _task_log_status(
        channel,
        task.schedule if task is not None else None,
        success_run,
        now,
        day_start,
    )
    return NewsChannelResponse(
        key=channel.key,
        name=channel.name,
        status=status,
        status_text=_STATUS_TEXT[status],
        poll_desc=channel.poll_desc,
        today_count=today_count,
        last_updated_at=last_at,
        lag_seconds=_lag_seconds(now, last_at),
    )


async def get_channels_status(
    session: AsyncSession, now: datetime | None = None
) -> NewsChannelsResponse:
    """全部注册渠道的监控卡 + 今日统计（今日按 CN 日界）。"""
    now = now or now_cn()
    day_start = _day_start(now)
    task_repo = CollectorTaskRepository(session)
    channels: list[NewsChannelResponse] = []
    for channel in NEWS_CHANNELS:
        if channel.monitor_type == MONITOR_STREAM:
            item = await _status_stream(channel, session, now, day_start)
        else:
            item = await _status_task_log(channel, session, now, day_start, task_repo)
        channels.append(item)
    total, scored, high = await ai_score_repository.today_stats(
        session, day_start=day_start
    )
    return NewsChannelsResponse(
        channels=channels,
        stats=NewsStatsResponse(
            today_total=total,
            scored_count=scored,
            high_count=high,
        ),
    )
