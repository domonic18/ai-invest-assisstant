"""Collector log business services."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collector_log import CollectorLog
from app.repositories.collector_log_repository import CollectorLogRepository


class CollectorLogService:
    """采集执行日志查询服务。"""

    MAX_LIMIT = 200

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = CollectorLogRepository(session)

    async def list_recent(self, limit: int = 50) -> list[CollectorLog]:
        """查询最近的采集执行日志，按开始时间倒序。"""
        if limit <= 0 or limit > self.MAX_LIMIT:
            raise ValueError(f"limit must be between 1 and {self.MAX_LIMIT}")
        return await self.repo.list_recent(limit)
