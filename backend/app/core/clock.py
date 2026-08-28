"""业务时钟：A 股业务日期统一按 Asia/Shanghai 解析。

``date.today()`` 依赖容器本地时区，``datetime.now(timezone.utc).date()``
在 00:00-08:00 CST 之间会落在前一个日历日；两者都不适合作为业务"今天"。
所有业务日期（交易日判定、K 线/竞价/研报的默认日期区间）必须使用本模块；
数据库与日志的时间戳字段（timestamptz）仍统一使用 UTC
（``datetime.now(timezone.utc)``，禁止 naive 的 ``datetime.utcnow()``）。
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

CN_TZ = ZoneInfo("Asia/Shanghai")

__all__ = [
    "CN_TZ",
    "now_cn",
    "today_cn",
]


def now_cn() -> datetime:
    """当前 Asia/Shanghai 时间（带时区）。"""
    return datetime.now(CN_TZ)


def today_cn() -> date:
    """当前 Asia/Shanghai 日历日，即 A 股业务"今天"。"""
    return now_cn().date()
