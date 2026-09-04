"""采集任务仓储。"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collector_task import CollectorTask
from app.repositories.base import BaseRepository


class CollectorTaskRepository(BaseRepository[CollectorTask]):
    """采集任务的数据访问。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CollectorTask)

    async def list_paginated(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[CollectorTask], int]:
        """按 id 排序返回分页的采集任务。"""
        stmt = select(CollectorTask).order_by(CollectorTask.id).offset(offset).limit(limit)
        count_stmt = select(func.count()).select_from(CollectorTask)
        result = await self.execute(stmt)
        total = (await self.scalar(count_stmt)) or 0
        return list(result.scalars().all()), total

    async def list_active_scheduled(self) -> list[CollectorTask]:
        """已启用且配置了 cron 计划的任务。"""
        stmt = (
            select(CollectorTask)
            .where(CollectorTask.is_active.is_(True), CollectorTask.schedule.is_not(None))
            .order_by(CollectorTask.id)
        )
        result = await self.execute(stmt)
        return list(result.scalars().all())
