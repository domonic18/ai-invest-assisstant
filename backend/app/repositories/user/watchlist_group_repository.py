"""自选股分组仓储。"""

from typing import cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.watchlist import UserWatchlistGroup
from app.repositories.base import BaseRepository


class WatchlistGroupRepository(BaseRepository[UserWatchlistGroup]):
    """用户自选股分组的数据访问。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, UserWatchlistGroup)

    async def list_by_user(self, user_id: int) -> list[UserWatchlistGroup]:
        """按排序值升序返回用户分组列表。"""
        stmt = (
            select(UserWatchlistGroup)
            .where(UserWatchlistGroup.user_id == user_id)
            .order_by(UserWatchlistGroup.sort_order, UserWatchlistGroup.id)
        )
        result = await self.execute(stmt)
        return list(result.scalars().all())

    async def get_by_user_and_id(self, user_id: int, group_id: int) -> UserWatchlistGroup | None:
        """返回指定用户的分组（越权防护：不属于该用户返回 None）。"""
        stmt = select(UserWatchlistGroup).where(
            UserWatchlistGroup.user_id == user_id,
            UserWatchlistGroup.id == group_id,
        )
        result = await self.execute(stmt)
        return cast(UserWatchlistGroup | None, result.scalar_one_or_none())

    async def get_default(self, user_id: int) -> UserWatchlistGroup | None:
        """返回用户默认分组。"""
        stmt = select(UserWatchlistGroup).where(
            UserWatchlistGroup.user_id == user_id,
            UserWatchlistGroup.is_default.is_(True),
        )
        result = await self.execute(stmt)
        return cast(UserWatchlistGroup | None, result.scalar_one_or_none())

    async def get_by_name(self, user_id: int, name: str) -> UserWatchlistGroup | None:
        """返回用户同名分组。"""
        stmt = select(UserWatchlistGroup).where(
            UserWatchlistGroup.user_id == user_id,
            UserWatchlistGroup.name == name,
        )
        result = await self.execute(stmt)
        return cast(UserWatchlistGroup | None, result.scalar_one_or_none())

    async def count_by_user(self, user_id: int) -> int:
        """返回用户分组数量。"""
        stmt = select(func.count()).select_from(UserWatchlistGroup).where(
            UserWatchlistGroup.user_id == user_id
        )
        return (await self.session.scalar(stmt)) or 0
