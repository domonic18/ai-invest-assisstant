"""大盘涨跌统计与成交额查询仓储（market_breadth / market_amount）。"""

from datetime import date
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_amount import MarketAmount
from app.models.market_breadth import MarketBreadth


async def get_latest_breadth_on_or_before(
    session: AsyncSession, resolved: date
) -> MarketBreadth | None:
    """不晚于 resolved 的最新一行涨跌统计（盘前/周末取上一交易日收盘快照）。"""
    return cast(
        MarketBreadth | None,
        await session.scalar(
            select(MarketBreadth)
            .where(MarketBreadth.trade_date <= resolved)
            .order_by(MarketBreadth.trade_date.desc())
            .limit(1)
        ),
    )


async def get_breadth_by_date(
    session: AsyncSession, trade_date: date
) -> MarketBreadth | None:
    """指定交易日的涨跌统计行。"""
    return cast(
        MarketBreadth | None,
        await session.scalar(
            select(MarketBreadth).where(MarketBreadth.trade_date == trade_date)
        ),
    )


async def get_broken_limit_count(
    session: AsyncSession, trade_date: date
) -> int | None:
    """指定交易日的炸板家数（盘后任务写入，无行时为 None）。"""
    return await session.scalar(
        select(MarketBreadth.broken_limit_count).where(
            MarketBreadth.trade_date == trade_date
        )
    )


async def has_breadth_on(session: AsyncSession, day: date) -> bool:
    """当日是否已有涨跌统计行（采集器盘中写入，交易日判定的回退依据）。"""
    count = await session.scalar(
        select(func.count())
        .select_from(MarketBreadth)
        .where(MarketBreadth.trade_date == day)
    )
    return bool(count)


async def list_recent_amounts(
    session: AsyncSession, resolved: date, limit: int = 2
) -> list[MarketAmount]:
    """不晚于 resolved 的最近 limit 个交易日官方成交额（倒序）。"""
    rows = (
        await session.execute(
            select(MarketAmount)
            .where(MarketAmount.trade_date <= resolved)
            .order_by(MarketAmount.trade_date.desc())
            .limit(limit)
        )
    ).scalars().all()
    return list(rows)
