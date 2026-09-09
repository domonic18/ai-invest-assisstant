"""采集渠道数据类型优先级仓储。"""

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collector_channel_data_type import CollectorChannelDataType
from app.repositories.base import BaseRepository


class CollectorChannelDataTypeRepository(BaseRepository[CollectorChannelDataType]):
    """渠道数据类型优先级关联的数据访问。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CollectorChannelDataType)

    async def list_all(self, limit: int = 2000) -> list[CollectorChannelDataType]:
        """返回所有关联，先按数据类型再按优先级排序（配置表，封顶防御）。"""
        stmt = (
            select(CollectorChannelDataType)
            .order_by(
                CollectorChannelDataType.data_type,
                CollectorChannelDataType.priority,
                CollectorChannelDataType.channel_id,
            )
            .limit(limit)
        )
        result = await self.execute(stmt)
        return list(result.scalars().all())

    async def list_for_data_type(
        self, data_type: str
    ) -> list[CollectorChannelDataType]:
        """返回指定数据类型的关联，按优先级排序。"""
        stmt = (
            select(CollectorChannelDataType)
            .where(CollectorChannelDataType.data_type == data_type)
            .order_by(
                CollectorChannelDataType.priority,
                CollectorChannelDataType.channel_id,
            )
        )
        result = await self.execute(stmt)
        return list(result.scalars().all())

    async def list_for_channel(
        self, channel_id: int
    ) -> list[CollectorChannelDataType]:
        """返回指定渠道的全部关联。"""
        stmt = select(CollectorChannelDataType).where(
            CollectorChannelDataType.channel_id == channel_id
        )
        result = await self.execute(stmt)
        return list(result.scalars().all())

    async def list_for_channels(
        self, channel_ids: set[int]
    ) -> list[CollectorChannelDataType]:
        """批量返回多个渠道的全部关联。"""
        if not channel_ids:
            return []
        stmt = select(CollectorChannelDataType).where(
            CollectorChannelDataType.channel_id.in_(channel_ids)
        )
        result = await self.execute(stmt)
        return list(result.scalars().all())

    async def delete_for_data_type(self, data_type: str) -> None:
        """删除指定数据类型的全部关联。"""
        await self.session.execute(
            delete(CollectorChannelDataType).where(
                CollectorChannelDataType.data_type == data_type
            )
        )

    async def max_priority(self, data_type: str) -> int:
        """返回指定数据类型当前的最大优先级（为空时返回 0）。"""
        result = await self.execute(
            select(func.max(CollectorChannelDataType.priority)).where(
                CollectorChannelDataType.data_type == data_type
            )
        )
        return int(result.scalar_one_or_none() or 0)

    async def max_priorities(self, data_types: set[str]) -> dict[str, int]:
        """批量返回各数据类型的最大优先级（无关联的类型不在结果中）。"""
        if not data_types:
            return {}
        stmt = (
            select(
                CollectorChannelDataType.data_type,
                func.max(CollectorChannelDataType.priority),
            )
            .where(CollectorChannelDataType.data_type.in_(data_types))
            .group_by(CollectorChannelDataType.data_type)
        )
        result = await self.execute(stmt)
        return {data_type: int(max_p) for data_type, max_p in result.all()}

    async def get_distinct_data_types(self) -> set[str]:
        """返回关联表中出现的所有数据类型集合。"""
        result = await self.execute(select(CollectorChannelDataType.data_type).distinct())
        return {row[0] for row in result.all()}
