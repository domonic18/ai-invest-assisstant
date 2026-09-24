"""K 线画线仓储（用户画线 / AI 画线两表的数据访问，不管理事务）。"""

from typing import cast

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kline_drawing import AiKlineDrawing, UserKlineDrawing
from app.repositories.base import BaseRepository


class UserKlineDrawingRepository(BaseRepository[UserKlineDrawing]):
    """用户画线的数据访问（查改删均限定 user 归属）。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, UserKlineDrawing)

    async def list_by_user_target(
        self, user_id: int, target_type: str, target_code: str
    ) -> list[UserKlineDrawing]:
        """返回指定用户在该标的全周期的画线（按创建时间升序）。"""
        stmt = (
            select(UserKlineDrawing)
            .where(
                UserKlineDrawing.user_id == user_id,
                UserKlineDrawing.target_type == target_type,
                UserKlineDrawing.target_code == target_code,
            )
            .order_by(UserKlineDrawing.created_at.asc())
        )
        result = await self.execute(stmt)
        return list(result.scalars().all())

    async def get_for_user(self, user_id: int, drawing_id: int) -> UserKlineDrawing | None:
        """按 id 取用户画线，校验归属；非本人返回 None。"""
        stmt = select(UserKlineDrawing).where(
            UserKlineDrawing.id == drawing_id,
            UserKlineDrawing.user_id == user_id,
        )
        result = await self.execute(stmt)
        return cast(UserKlineDrawing | None, result.scalar_one_or_none())

    async def delete_all_for_target(
        self, user_id: int, target_type: str, target_code: str, periods: list[str] | None = None
    ) -> int:
        """删除用户在该标的（可限定周期）的全部画线，返回删除行数。"""
        stmt = delete(UserKlineDrawing).where(
            UserKlineDrawing.user_id == user_id,
            UserKlineDrawing.target_type == target_type,
            UserKlineDrawing.target_code == target_code,
        )
        if periods:
            stmt = stmt.where(UserKlineDrawing.period.in_(periods))
        result = await self.execute(stmt)
        return int(result.rowcount or 0)


class AiKlineDrawingRepository(BaseRepository[AiKlineDrawing]):
    """AI 画线集的数据访问（每用户每标的每周期一行，多租户隔离）。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AiKlineDrawing)

    async def list_by_user_target(
        self, user_id: int, target_type: str, target_code: str
    ) -> list[AiKlineDrawing]:
        """返回指定用户在该标的全周期的 AI 画线集（按周期升序）。"""
        stmt = (
            select(AiKlineDrawing)
            .where(
                AiKlineDrawing.user_id == user_id,
                AiKlineDrawing.target_type == target_type,
                AiKlineDrawing.target_code == target_code,
            )
            .order_by(AiKlineDrawing.period.asc())
        )
        result = await self.execute(stmt)
        return list(result.scalars().all())

    async def get_group(
        self, user_id: int, target_type: str, target_code: str, period: str
    ) -> AiKlineDrawing | None:
        """返回指定用户在标的+周期的 AI 画线集。"""
        stmt = select(AiKlineDrawing).where(
            AiKlineDrawing.user_id == user_id,
            AiKlineDrawing.target_type == target_type,
            AiKlineDrawing.target_code == target_code,
            AiKlineDrawing.period == period,
        )
        result = await self.execute(stmt)
        return cast(AiKlineDrawing | None, result.scalar_one_or_none())
