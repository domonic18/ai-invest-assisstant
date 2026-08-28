"""K 线查询仓储：日线读取与多周期聚合（TimescaleDB time_bucket）。

周/月/季/年线不做冗余存储，由 quote_kline_stock_daily 在查询时聚合：
time_bucket 的默认 origin 使 1 week 对齐自然周（周一起）、
3 months 对齐自然季（1/4/7/10 月起）、1 year 对齐自然年。
"""

from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import CN_TZ, today_cn
from app.models.kline import KlineDaily, KlineMinute

# quote_kline_stock_minute.trade_time 为 TIMESTAMPTZ，按交易时区（Asia/Shanghai）界定自然日

# period -> time_bucket 间隔；daily 不走聚合
PERIOD_BUCKET: dict[str, str] = {
    "weekly": "1 week",
    "monthly": "1 month",
    "quarterly": "3 months",
    "yearly": "1 year",
}

# bucket 间隔对应的自然日数（用于推算聚合查询的时间下界）
_BUCKET_DAYS: dict[str, int] = {
    "1 week": 7,
    "1 month": 31,
    "3 months": 93,
    "1 year": 366,
}

_AGGREGATED_SQL = text(
    """
    SELECT
        time_bucket(CAST(CAST(:bucket AS text) AS interval), trade_date) AS bucket_date,
        first(open, trade_date)  AS open,
        max(high)                AS high,
        min(low)                 AS low,
        last(close, trade_date)  AS close,
        sum(volume)              AS volume,
        sum(amount)              AS amount
    FROM quote_kline_stock_daily
    WHERE stock_code = :code
      AND trade_date >= CAST(:since AS date)
    GROUP BY bucket_date
    ORDER BY bucket_date DESC
    LIMIT :limit
    """
)


def _daily_since(end_date: date | None, limit: int) -> date:
    """日 K 查询时间下界：limit 根交易日最多跨 limit*2 个自然日。

    无时间下界时 TimescaleDB 无法做 chunk 排除，数千个 chunk 的
    规划耗时可达数百毫秒；下界保证命中的 chunk 数量与 limit 成正比。
    """
    return (end_date or today_cn()) - timedelta(days=limit * 2)


async def fetch_daily_bars(
    session: AsyncSession,
    code: str,
    end_date: date | None = None,
    limit: int = 250,
) -> list[KlineDaily]:
    """按日期倒序读取日 K（limit 截断），调用方需要升序时自行反转。"""
    stmt = (
        select(KlineDaily)
        .where(KlineDaily.stock_code == code)
        .where(KlineDaily.trade_date >= _daily_since(end_date, limit))
    )
    if end_date is not None:
        stmt = stmt.where(KlineDaily.trade_date <= end_date)
    stmt = stmt.order_by(KlineDaily.trade_date.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def fetch_aggregated_bars(
    session: AsyncSession,
    code: str,
    bucket: str,
    limit: int = 250,
) -> list[dict[str, Any]]:
    """按 time_bucket 间隔聚合日 K 为多周期 K 线（倒序，limit 截断）。

    时间下界 = limit 个 bucket 跨度 + 31 天余量，触发 chunk 排除，
    避免全量 chunk 规划开销。
    """
    since = today_cn() - timedelta(days=_BUCKET_DAYS[bucket] * limit + 31)
    result = await session.execute(
        _AGGREGATED_SQL,
        {"code": code, "bucket": bucket, "since": since, "limit": limit},
    )
    return [dict(row) for row in result.mappings().all()]


async def fetch_minute_bars(
    session: AsyncSession, code: str, day: date
) -> list[KlineMinute]:
    """读取某交易日全部分钟 K（升序）。"""
    stmt = (
        select(KlineMinute)
        .where(
            KlineMinute.stock_code == code,
            KlineMinute.trade_time >= datetime.combine(day, time.min, tzinfo=CN_TZ),
            KlineMinute.trade_time
            < datetime.combine(day + timedelta(days=1), time.min, tzinfo=CN_TZ),
        )
        .order_by(KlineMinute.trade_time)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def fetch_minute_bars_multi(
    session: AsyncSession, codes: list[str], day: date
) -> list[KlineMinute]:
    """读取多只标的某交易日全部分钟 K（按代码分组、组内升序）。"""
    if not codes:
        return []
    stmt = (
        select(KlineMinute)
        .where(
            KlineMinute.stock_code.in_(codes),
            KlineMinute.trade_time >= datetime.combine(day, time.min, tzinfo=CN_TZ),
            KlineMinute.trade_time
            < datetime.combine(day + timedelta(days=1), time.min, tzinfo=CN_TZ),
        )
        .order_by(KlineMinute.stock_code, KlineMinute.trade_time)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def latest_minute_day(session: AsyncSession, code: str) -> date | None:
    """quote_kline_stock_minute 中该代码最近一根 bar 的交易日期（交易时区）。"""
    latest = await session.scalar(
        select(func.max(KlineMinute.trade_time)).where(
            KlineMinute.stock_code == code
        )
    )
    return latest.astimezone(CN_TZ).date() if latest is not None else None


async def prev_minute_close(
    session: AsyncSession, code: str, day: date
) -> float | None:
    """目标日期之前最近一根分钟 bar 的收盘价（昨收口径）。"""
    close = await session.scalar(
        select(KlineMinute.close)
        .where(
            KlineMinute.stock_code == code,
            KlineMinute.trade_time < datetime.combine(day, time.min, tzinfo=CN_TZ),
        )
        .order_by(KlineMinute.trade_time.desc())
        .limit(1)
    )
    return float(close) if close is not None else None


async def fetch_max_daily_date(session: AsyncSession, code: str) -> date | None:
    """quote_kline_stock_daily 中该代码最近一根日 K 的交易日期。"""
    max_date = await session.scalar(
        select(func.max(KlineDaily.trade_date)).where(KlineDaily.stock_code == code)
    )
    return max_date if isinstance(max_date, date) else None


async def has_daily_bar(session: AsyncSession, code: str, day: date) -> bool:
    """判断该代码在指定日期是否存在日 K。"""
    count = await session.scalar(
        select(func.count())
        .select_from(KlineDaily)
        .where(KlineDaily.stock_code == code, KlineDaily.trade_date == day)
    )
    return (count or 0) > 0
