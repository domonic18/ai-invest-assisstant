"""Collector log business services."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collector_dead_letter import CollectorDeadLetter
from app.models.collector_log import CollectorLog
from app.repositories.admin.collector_dead_letter_repository import (
    CollectorDeadLetterRepository,
)
from app.repositories.admin.collector_log_repository import CollectorLogRepository


class CollectorLogService:
    """采集执行日志与死信查询服务。"""

    MAX_LIMIT = 200

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = CollectorLogRepository(session)
        self.dead_letter_repo = CollectorDeadLetterRepository(session)

    async def list_recent(self, limit: int = 50) -> list[CollectorLog]:
        """查询最近的采集执行日志，按开始时间倒序。"""
        if limit <= 0 or limit > self.MAX_LIMIT:
            raise ValueError(f"limit must be between 1 and {self.MAX_LIMIT}")
        return await self.repo.list_recent(limit)

    async def get_by_id(self, log_id: int) -> CollectorLog | None:
        """按主键查询单条采集执行日志。"""
        return await self.repo.get_by_id(log_id)

    async def list_dead_letters(
        self, page: int = 1, page_size: int = 20
    ) -> tuple[int, list[CollectorDeadLetter]]:
        """分页查询采集死信，按创建时间倒序。"""
        offset = (page - 1) * page_size
        return await self.dead_letter_repo.list_paginated(offset, page_size)
