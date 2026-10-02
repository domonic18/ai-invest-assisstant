"""业务时钟：A 股业务日期统一按 Asia/Shanghai 解析。

``date.today()`` 依赖容器本地时区，``datetime.now(timezone.utc).date()``
在 00:00-08:00 CST 之间会落在前一个日历日；两者都不适合作为业务"今天"。
所有业务日期（交易日判定、K 线/竞价/研报的默认日期区间）必须使用本模块；
数据库与日志的时间戳字段（timestamptz）仍统一使用 UTC
（``datetime.now(timezone.utc)``，禁止 naive 的 ``datetime.utcnow()``）。
"""

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

CN_TZ = ZoneInfo("Asia/Shanghai")

__all__ = [
    "CN_TZ",
    "in_tail_check_window",
    "in_trading_session",
    "now_cn",
    "today_cn",
    "utc_now",
]

# A 股连续竞价时段（北京时间，不含集合竞价 9:15-9:25 与午休）
_MORNING_OPEN = time(9, 30)
_MORNING_CLOSE = time(11, 30)
_AFTERNOON_OPEN = time(13, 0)
_AFTERNOON_CLOSE = time(15, 0)
# 尾盘强检窗口：收盘前 10 分钟（持仓止损强检 + 未触发计划失效）
_TAIL_CHECK_START = time(14, 50)


def now_cn() -> datetime:
    """当前 Asia/Shanghai 时间（带时区）。"""
    return datetime.now(CN_TZ)


def today_cn() -> date:
    """当前 Asia/Shanghai 日历日，即 A 股业务"今天"。"""
    return now_cn().date()


def utc_now() -> datetime:
    """当前 aware UTC 时间；timestamptz 列默认值与日志时间戳统一使用本函数。"""
    return datetime.now(timezone.utc)


def in_trading_session(now: datetime | None = None) -> bool:
    """给定时刻（缺省当前）是否处于 A 股连续竞价时段（9:30-11:30 / 13:00-15:00 北京时间）。

    纯时钟谓词：只判时刻不判交易日（交易日历由调用方传入，见
    collector.core.calendar.is_trading_day），周末/节假日由调用方保证。
    """
    t = (now or now_cn()).astimezone(CN_TZ).time()
    return _MORNING_OPEN <= t < _MORNING_CLOSE or _AFTERNOON_OPEN <= t < _AFTERNOON_CLOSE


def in_tail_check_window(now: datetime | None = None) -> bool:
    """给定时刻（缺省当前）是否处于尾盘强检窗口（14:50-15:00 北京时间）。"""
    t = (now or now_cn()).astimezone(CN_TZ).time()
    return _TAIL_CHECK_START <= t < _AFTERNOON_CLOSE
