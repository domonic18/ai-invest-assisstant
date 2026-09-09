"""全球指标配置与最新收盘快照查询仓储。"""

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quote_global_index import GlobalIndexDaily
from app.models.tracked_index import TrackedIndexConfig


async def list_enabled_global_configs(
    session: AsyncSession,
) -> list[TrackedIndexConfig]:
    """启用中的全球指标配置（按 sort_order 排序）。"""
    stmt = (
        select(TrackedIndexConfig)
        .where(
            TrackedIndexConfig.market_category == "全球",
            TrackedIndexConfig.is_enabled.is_(True),
        )
        .order_by(TrackedIndexConfig.sort_order, TrackedIndexConfig.id)
    )
    return list((await session.execute(stmt)).scalars().all())


async def map_latest_closes(
    session: AsyncSession, codes: list[str]
) -> dict[str, tuple[Decimal | None, Decimal | None, date | None]]:
    """每只指标代码的最新日 K 收盘快照（close, change_pct, trade_date）。"""
    if not codes:
        return {}
    stmt = (
        select(
            GlobalIndexDaily.index_code,
            GlobalIndexDaily.close,
            GlobalIndexDaily.change_pct,
            GlobalIndexDaily.trade_date,
        )
        .where(GlobalIndexDaily.index_code.in_(codes))
        .distinct(GlobalIndexDaily.index_code)
        .order_by(GlobalIndexDaily.index_code, GlobalIndexDaily.trade_date.desc())
    )
    return {
        row[0]: (row[1], row[2], row[3])
        for row in (await session.execute(stmt)).all()
    }


async def map_recent_closes(
    session: AsyncSession, codes: list[str], limit: int
) -> dict[str, list[float]]:
    """每只指标最近 limit 个收盘（升序，None 收盘剔除），供趋势缩略图。"""
    if not codes:
        return {}
    rn = (
        func.row_number()
        .over(
            partition_by=GlobalIndexDaily.index_code,
            order_by=GlobalIndexDaily.trade_date.desc(),
        )
        .label("rn")
    )
    ranked = (
        select(
            GlobalIndexDaily.index_code.label("index_code"),
            GlobalIndexDaily.trade_date.label("trade_date"),
            GlobalIndexDaily.close.label("close"),
            rn,
        )
        .where(GlobalIndexDaily.index_code.in_(codes))
        .subquery()
    )
    rows = await session.execute(
        select(ranked.c.index_code, ranked.c.close)
        .where(ranked.c.rn <= limit)
        .order_by(ranked.c.index_code, ranked.c.trade_date)
    )
    trends: dict[str, list[float]] = {}
    for code, close in rows.all():
        if close is not None:
            trends.setdefault(code, []).append(float(close))
    return trends


async def list_closes(
    session: AsyncSession, code: str, since: date
) -> list[tuple[date, Decimal]]:
    """指定指标自 since 起的日线收盘（trade_date 升序）。"""
    stmt = (
        select(GlobalIndexDaily.trade_date, GlobalIndexDaily.close)
        .where(
            GlobalIndexDaily.index_code == code,
            GlobalIndexDaily.trade_date >= since,
        )
        .order_by(GlobalIndexDaily.trade_date)
    )
    return [(row[0], row[1]) for row in (await session.execute(stmt)).all()]


async def list_daily_bars(
    session: AsyncSession, code: str, since: date
) -> list[GlobalIndexDaily]:
    """指定指标自 since 起的日线 OHLCV（trade_date 升序）。"""
    stmt = (
        select(GlobalIndexDaily)
        .where(
            GlobalIndexDaily.index_code == code,
            GlobalIndexDaily.trade_date >= since,
        )
        .order_by(GlobalIndexDaily.trade_date)
    )
    return list((await session.execute(stmt)).scalars().all())
