"""User watchlist business services."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.watchlist import UserWatchlist
from app.schemas.user import WatchlistItemCreate


async def get_watchlist_by_user(session: AsyncSession, user_id: int) -> list[UserWatchlist]:
    """获取用户自选股列表。"""
    result = await session.execute(
        select(UserWatchlist)
        .where(UserWatchlist.user_id == user_id)
        .order_by(UserWatchlist.created_at.desc())
    )
    return list(result.scalars().all())


async def add_watchlist_item(
    session: AsyncSession, user: User, data: WatchlistItemCreate
) -> UserWatchlist:
    """添加自选股。"""
    existing = await session.execute(
        select(UserWatchlist).where(
            UserWatchlist.user_id == user.id,
            UserWatchlist.stock_code == data.stock_code,
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError("Stock already in watchlist")

    item = UserWatchlist(
        user_id=user.id,
        stock_code=data.stock_code,
        tags=data.tags,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item
