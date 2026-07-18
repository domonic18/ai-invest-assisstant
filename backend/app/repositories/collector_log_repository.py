"""Collector log repository."""

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collector_log import CollectorLog
from app.repositories.base import BaseRepository


class CollectorLogRepository(BaseRepository[CollectorLog]):
    """Data access for collector execution logs."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CollectorLog)

    async def list_recent(self, limit: int = 50) -> list[CollectorLog]:
        """Return recent logs ordered by start time, newest first."""
        stmt = select(CollectorLog).order_by(desc(CollectorLog.started_at)).limit(limit)
        result = await self.execute(stmt)
        return list(result.scalars().all())
