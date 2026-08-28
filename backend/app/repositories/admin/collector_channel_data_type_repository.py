"""Collector channel data-type priority repository."""

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collector_channel_data_type import CollectorChannelDataType
from app.repositories.base import BaseRepository


class CollectorChannelDataTypeRepository(BaseRepository[CollectorChannelDataType]):
    """Data access for channel data-type priority associations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CollectorChannelDataType)

    async def list_all(self) -> list[CollectorChannelDataType]:
        """Return all associations ordered by data_type then priority."""
        stmt = select(CollectorChannelDataType).order_by(
            CollectorChannelDataType.data_type,
            CollectorChannelDataType.priority,
            CollectorChannelDataType.channel_id,
        )
        result = await self.execute(stmt)
        return list(result.scalars().all())

    async def list_for_data_type(
        self, data_type: str
    ) -> list[CollectorChannelDataType]:
        """Return associations for a data type ordered by priority."""
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
        """Return all associations for a channel."""
        stmt = select(CollectorChannelDataType).where(
            CollectorChannelDataType.channel_id == channel_id
        )
        result = await self.execute(stmt)
        return list(result.scalars().all())

    async def delete_for_data_type(self, data_type: str) -> None:
        """Remove all associations for a data type."""
        await self.session.execute(
            delete(CollectorChannelDataType).where(
                CollectorChannelDataType.data_type == data_type
            )
        )

    async def max_priority(self, data_type: str) -> int:
        """Return the current max priority for a data type (0 when empty)."""
        result = await self.execute(
            select(func.max(CollectorChannelDataType.priority)).where(
                CollectorChannelDataType.data_type == data_type
            )
        )
        return int(result.scalar_one_or_none() or 0)

    async def get_distinct_data_types(self) -> set[str]:
        """Return the set of data types present in the association table."""
        result = await self.execute(select(CollectorChannelDataType.data_type).distinct())
        return {row[0] for row in result.all()}
