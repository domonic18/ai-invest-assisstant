"""K 线查询仓储：日线读取与多周期聚合（TimescaleDB time_bucket）。

周/月/季/年线不做冗余存储，由 quote_kline_stock_daily 在查询时聚合：
time_bucket 的默认 origin 使 1 week 对齐自然周（周一起）、
3 months 对齐自然季（1/4/7/10 月起）、1 year 对齐自然年。
"""

from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.clock import CN_TZ, today_cn
from app.models.kline import KlineDaily, KlineMinute, SectorKlineDaily

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


async def fetch_daily_bars_multi(
    session: AsyncSession,
    codes: list[str],
    end_date: date | None = None,
    limit: int = 250,
) -> dict[str, list[KlineDaily]]:
    """批量读取多标的日 K（每标的各取倒序 limit 根），按代码分组的升序列表。

    单次 IN + 窗口函数（row_number per stock_code）替代逐标的查询，
    复用 `_daily_since` 时间下界触发 chunk 排除。
    """
    if not codes:
        return {}
    rn = (
        func.row_number()
        .over(
            partition_by=KlineDaily.stock_code,
            order_by=KlineDaily.trade_date.desc(),
        )
        .label("rn")
    )
    inner = (
        select(KlineDaily)
        .where(
            KlineDaily.stock_code.in_(codes),
            KlineDaily.trade_date >= _daily_since(end_date, limit),
        )
        .add_columns(rn)
        .subquery()
    )
    daily = aliased(KlineDaily, inner)
    stmt = (
        select(daily)
        .select_from(inner)
        .where(inner.c.rn <= limit)
        .order_by(daily.stock_code, daily.trade_date)
    )
    bars_by_code: dict[str, list[KlineDaily]] = {}
    for row in (await session.execute(stmt)).scalars().all():
        bars_by_code.setdefault(row.stock_code, []).append(row)
    return bars_by_code


async def list_daily_paginated(
    session: AsyncSession,
    stock_code: str,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[KlineDaily], int]:
    """按代码分页查询日 K（trade_date 倒序，总数与列表同条件）。"""
    stmt = select(KlineDaily).where(KlineDaily.stock_code == stock_code)
    count_stmt = (
        select(func.count())
        .select_from(KlineDaily)
        .where(KlineDaily.stock_code == stock_code)
    )
    if start_date:
        stmt = stmt.where(KlineDaily.trade_date >= start_date)
        count_stmt = count_stmt.where(KlineDaily.trade_date >= start_date)
    if end_date:
        stmt = stmt.where(KlineDaily.trade_date <= end_date)
        count_stmt = count_stmt.where(KlineDaily.trade_date <= end_date)
    stmt = (
        stmt.order_by(KlineDaily.trade_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    total = (await session.scalar(count_stmt)) or 0
    return list(result.scalars().all()), total


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


async def fetch_max_daily_date_on_or_before(
    session: AsyncSession, code: str, day: date
) -> date | None:
    """该代码不晚于 day 的最近一根日 K 交易日期。"""
    max_date = await session.scalar(
        select(func.max(KlineDaily.trade_date)).where(
            KlineDaily.stock_code == code, KlineDaily.trade_date <= day
        )
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


async def list_sector_kline_by_name(
    session: AsyncSession, sector_name: str, limit: int = 250
) -> list[SectorKlineDaily]:
    """按板块名取同花顺板块指数日 K（近 N 根升序），板块详情页桥接查询。"""
    stmt = (
        select(SectorKlineDaily)
        .where(SectorKlineDaily.sector_name == sector_name)
        .order_by(SectorKlineDaily.trade_date.desc())
        .limit(limit)
    )
    return list(reversed((await session.execute(stmt)).scalars().all()))


async def list_ths_sector_names(session: AsyncSession) -> list[tuple[str, str]]:
    """同花顺指数覆盖的 (sector_type, sector_name) 宇宙（板块异动检测池收敛判据）。"""
    stmt = select(SectorKlineDaily.sector_type, SectorKlineDaily.sector_name).distinct()
    return [(row[0], row[1]) for row in (await session.execute(stmt)).all()]
