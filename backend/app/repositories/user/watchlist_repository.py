"""Watchlist repository."""

from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.watchlist import UserWatchlist
from app.repositories.base import BaseRepository


class WatchlistRepository(BaseRepository[UserWatchlist]):
    """Data access for user watchlists."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, UserWatchlist)

    async def list_by_user(self, user_id: int) -> list[UserWatchlist]:
        """Return a user's watchlist ordered by creation time desc."""
        stmt = (
            select(UserWatchlist)
            .where(UserWatchlist.user_id == user_id)
            .order_by(UserWatchlist.created_at.desc())
        )
        result = await self.execute(stmt)
        return list(result.scalars().all())

    async def get_by_user_and_stock(
        self, user_id: int, stock_code: str
    ) -> UserWatchlist | None:
        """Return a watchlist item for a specific user and stock."""
        stmt = select(UserWatchlist).where(
            UserWatchlist.user_id == user_id,
            UserWatchlist.stock_code == stock_code,
        )
        result = await self.execute(stmt)
        return cast(UserWatchlist | None, result.scalar_one_or_none())
