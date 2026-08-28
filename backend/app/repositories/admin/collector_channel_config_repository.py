"""Collector channel configuration repository."""

from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collector_channel_config import CollectorChannelConfig
from app.repositories.base import BaseRepository


class CollectorChannelConfigRepository(BaseRepository[CollectorChannelConfig]):
    """Data access for collector channel configurations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CollectorChannelConfig)

    async def list_ordered(self) -> list[CollectorChannelConfig]:
        """Return all channel configurations ordered by source."""
        stmt = select(CollectorChannelConfig).order_by(CollectorChannelConfig.source)
        result = await self.execute(stmt)
        return list(result.scalars().all())

    async def get_enabled_by_source(self, source: str) -> CollectorChannelConfig | None:
        """Return the enabled configuration for a source, if any."""
        stmt = select(CollectorChannelConfig).where(
            CollectorChannelConfig.source == source,
            CollectorChannelConfig.is_enabled.is_(True),
        )
        result = await self.execute(stmt)
        return cast(CollectorChannelConfig | None, result.scalar_one_or_none())

    async def exists_by_source(self, source: str) -> bool:
        """Return True if a config with the given source exists."""
        result = await self.execute(
            select(CollectorChannelConfig.id)
            .where(CollectorChannelConfig.source == source)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None
