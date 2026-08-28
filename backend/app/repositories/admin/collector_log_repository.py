"""采集日志仓储。"""

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collector_log import CollectorLog
from app.repositories.base import BaseRepository


class CollectorLogRepository(BaseRepository[CollectorLog]):
    """采集执行日志的数据访问。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CollectorLog)

    async def list_recent(self, limit: int = 50) -> list[CollectorLog]:
        """按开始时间倒序返回最近的采集日志。"""
        stmt = select(CollectorLog).order_by(desc(CollectorLog.started_at)).limit(limit)
        result = await self.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, log_id: int) -> CollectorLog | None:
        """按主键返回单条采集日志。"""
        return await self.session.get(CollectorLog, log_id)
