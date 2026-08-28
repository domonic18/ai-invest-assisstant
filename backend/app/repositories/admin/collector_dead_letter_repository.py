"""Collector dead-letter repository."""

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collector_dead_letter import CollectorDeadLetter
from app.repositories.base import BaseRepository


class CollectorDeadLetterRepository(BaseRepository[CollectorDeadLetter]):
    """Data access for collector dead-letter entries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CollectorDeadLetter)

    async def list_paginated(
        self, offset: int = 0, limit: int = 20
    ) -> tuple[int, list[CollectorDeadLetter]]:
        """Return dead letters newest first with total count."""
        total = await self.session.scalar(select(func.count(CollectorDeadLetter.id)))
        stmt = (
            select(CollectorDeadLetter)
            .order_by(desc(CollectorDeadLetter.created_at))
            .offset(offset)
            .limit(limit)
        )
        result = await self.execute(stmt)
        return total or 0, list(result.scalars().all())
