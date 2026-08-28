"""采集渠道配置仓储。"""

from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collector_channel_config import CollectorChannelConfig
from app.repositories.base import BaseRepository


class CollectorChannelConfigRepository(BaseRepository[CollectorChannelConfig]):
    """采集渠道配置的数据访问。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CollectorChannelConfig)

    async def list_ordered(self) -> list[CollectorChannelConfig]:
        """按数据源排序返回所有渠道配置。"""
        stmt = select(CollectorChannelConfig).order_by(CollectorChannelConfig.source)
        result = await self.execute(stmt)
        return list(result.scalars().all())

    async def get_enabled_by_source(self, source: str) -> CollectorChannelConfig | None:
        """返回指定数据源已启用的配置，若不存在则为 None。"""
        stmt = select(CollectorChannelConfig).where(
            CollectorChannelConfig.source == source,
            CollectorChannelConfig.is_enabled.is_(True),
        )
        result = await self.execute(stmt)
        return cast(CollectorChannelConfig | None, result.scalar_one_or_none())

    async def exists_by_source(self, source: str) -> bool:
        """判断指定数据源的配置是否存在。"""
        result = await self.execute(
            select(CollectorChannelConfig.id)
            .where(CollectorChannelConfig.source == source)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None
