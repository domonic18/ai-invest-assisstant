"""CME FedWatch 快照与概率分布查询仓储。"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fed_watch import FedWatchProbability, FedWatchSnapshot


async def get_latest_snapshot(session: AsyncSession) -> FedWatchSnapshot | None:
    """最新一天的 FedWatch 快照元数据。"""
    stmt = select(FedWatchSnapshot).order_by(FedWatchSnapshot.as_of_date.desc()).limit(1)
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_probabilities(
    session: AsyncSession, as_of_date: date
) -> list[FedWatchProbability]:
    """指定快照日的全部会议 × 区间概率行（按会议日、区间升序）。"""
    stmt = (
        select(FedWatchProbability)
        .where(FedWatchProbability.as_of_date == as_of_date)
        .order_by(FedWatchProbability.meeting_date, FedWatchProbability.range_low)
    )
    return list((await session.execute(stmt)).scalars().all())
