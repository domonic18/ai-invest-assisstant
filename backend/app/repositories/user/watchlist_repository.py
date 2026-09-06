"""自选股仓储。"""

from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.watchlist import UserWatchlist, UserWatchlistGroup
from app.repositories.base import BaseRepository


class WatchlistRepository(BaseRepository[UserWatchlist]):
    """用户自选股的数据访问。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, UserWatchlist)

    async def list_by_user(self, user_id: int) -> list[UserWatchlist]:
        """按创建时间倒序返回用户自选股列表。"""
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
        """返回指定用户与股票的自选股记录。"""
        stmt = select(UserWatchlist).where(
            UserWatchlist.user_id == user_id,
            UserWatchlist.stock_code == stock_code,
        )
        result = await self.execute(stmt)
        return cast(UserWatchlist | None, result.scalar_one_or_none())

    async def map_by_user_and_codes(
        self, user_id: int, stock_codes: list[str]
    ) -> dict[str, UserWatchlist]:
        """批量返回指定用户已有自选记录（code -> 行），供批量导入去重判断。"""
        if not stock_codes:
            return {}
        stmt = select(UserWatchlist).where(
            UserWatchlist.user_id == user_id,
            UserWatchlist.stock_code.in_(stock_codes),
        )
        result = await self.execute(stmt)
        return {row.stock_code: row for row in result.scalars().all()}

    async def list_active_review_stock_codes(self) -> list[str]:
        """开启 AI 复盘分组内的去重股票代码（升序，定时任务遍历范围）。"""
        stmt = (
            select(UserWatchlist.stock_code)
            .join(UserWatchlistGroup, UserWatchlist.group_id == UserWatchlistGroup.id)
            .where(UserWatchlistGroup.ai_review_enabled.is_(True))
            .distinct()
            .order_by(UserWatchlist.stock_code)
        )
        result = await self.execute(stmt)
        return list(result.scalars())
