"""User watchlist business services."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.watchlist import UserWatchlist
from app.repositories.user.watchlist_repository import WatchlistRepository
from app.schemas.user import WatchlistItemCreate


class WatchlistService:
    """User watchlist business services."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = WatchlistRepository(session)

    async def get_watchlist_by_user(self, user_id: int) -> list[UserWatchlist]:
        """获取用户自选股列表。"""
        return await self.repo.list_by_user(user_id)

    async def add_watchlist_item(
        self, user: User, data: WatchlistItemCreate
    ) -> UserWatchlist:
        """添加自选股。"""
        existing = await self.repo.get_by_user_and_stock(user.id, data.stock_code)
        if existing:
            raise ValueError("Stock already in watchlist")

        item = UserWatchlist(
            user_id=user.id,
            stock_code=data.stock_code,
            tags=data.tags,
        )
        self.repo.add(item)
        await self.session.commit()
        await self.repo.refresh(item)
        return item
