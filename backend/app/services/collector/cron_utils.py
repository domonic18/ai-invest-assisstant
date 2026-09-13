"""cron 计划展开公共工具（北京时区口径）。

从资讯渠道监控服务抽取：渠道健康判定（news_channel_service）与采集健康
监测（services.collector.health）共用同一套「cron → 计划触发时刻」换算，
保证两处对"应执行时刻"的语义完全一致。
"""

from datetime import datetime, timedelta

from croniter import croniter

from app.core.clock import CN_TZ

# cron 缺失/非法时按 30 分钟节奏判定的回退间隔
DEFAULT_FALLBACK_INTERVAL = timedelta(minutes=30)


def expand_cron(schedule: str, base: datetime) -> list[datetime]:
    """从 base 起展开连续 4 个触发时刻（naive CN 时间）；非法返回空。"""
    try:
        it = croniter(schedule, base)
        return [it.get_next(datetime) for _ in range(4)]
    except Exception:  # noqa: BLE001
        return []


def day_base(day_start: datetime) -> datetime:
    """CN 日界回拨 1 秒作 cron 展开基点（纳入恰落在 00:00 的触发点）。"""
    return day_start.astimezone(CN_TZ).replace(tzinfo=None) - timedelta(seconds=1)


def cron_interval(
    schedule: str | None,
    day_start: datetime,
    fallback: timedelta = DEFAULT_FALLBACK_INTERVAL,
) -> timedelta:
    """cron 相邻触发的最大间隔（轮询型 delayed 阈值用）。"""
    if not schedule:
        return fallback
    times = expand_cron(schedule, day_base(day_start))
    if len(times) < 2:
        return fallback
    gaps = [b - a for a, b in zip(times, times[1:])]
    return max(gaps)
