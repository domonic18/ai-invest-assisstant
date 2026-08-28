"""News announcement repository."""

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news_announcement import NewsAnnouncement
from app.repositories.base import BaseRepository


class NewsAnnouncementRepository(BaseRepository[NewsAnnouncement]):
    """Data access for news announcements."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, NewsAnnouncement)

    def _apply_filters(
        self,
        stmt: Any,
        *,
        stock_code: str | None = None,
        doc_type: str | None = None,
        q: str | None = None,
        broker: str | None = None,
        industry: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> Any:
        """Apply common filters to a statement."""
        if stock_code:
            stmt = stmt.where(NewsAnnouncement.stock_code == stock_code)
        if doc_type:
            stmt = stmt.where(NewsAnnouncement.doc_type == doc_type)
        if q:
            pattern = f"%{q}%"
            stmt = stmt.where(
                NewsAnnouncement.title.ilike(pattern)
                | NewsAnnouncement.content.ilike(pattern)
            )
        if broker:
            stmt = stmt.where(NewsAnnouncement.extra["broker"].astext == broker)
        if industry:
            stmt = stmt.where(NewsAnnouncement.industry_tags.contains([industry]))
        if start_date:
            stmt = stmt.where(NewsAnnouncement.publish_date >= start_date)
        if end_date:
            end_datetime = end_date + timedelta(days=1)
            stmt = stmt.where(NewsAnnouncement.publish_date < end_datetime)
        return stmt

    async def list_paginated(
        self,
        *,
        stock_code: str | None = None,
        doc_type: str | None = None,
        q: str | None = None,
        broker: str | None = None,
        industry: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        order_by: Any | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[NewsAnnouncement], int]:
        """Return paginated news announcements with optional filters."""
        stmt = select(NewsAnnouncement)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        else:
            stmt = stmt.order_by(NewsAnnouncement.created_at.desc())
        count_stmt = select(func.count()).select_from(NewsAnnouncement)

        filters = {
            "stock_code": stock_code,
            "doc_type": doc_type,
            "q": q,
            "broker": broker,
            "industry": industry,
            "start_date": start_date,
            "end_date": end_date,
        }
        stmt = self._apply_filters(stmt, **filters)  # type: ignore[arg-type]
        count_stmt = self._apply_filters(count_stmt, **filters)  # type: ignore[arg-type]

        stmt = stmt.offset(offset).limit(limit)
        result = await self.execute(stmt)
        total = (await self.scalar(count_stmt)) or 0
        return list(result.scalars().all()), total

    async def list_research_filters(self) -> tuple[list[str], list[str]]:
        """Return distinct brokers and industry tags across research reports."""
        broker_stmt = (
            select(func.distinct(NewsAnnouncement.extra["broker"].astext))
            .where(NewsAnnouncement.doc_type == "research")
            .where(NewsAnnouncement.extra["broker"].astext.isnot(None))
        )
        industry_stmt = (
            select(func.distinct(NewsAnnouncement.industry_tags[1]))
            .where(NewsAnnouncement.doc_type == "research")
            .where(NewsAnnouncement.industry_tags.isnot(None))
        )
        brokers = (await self.session.execute(broker_stmt)).scalars().all()
        industries = (await self.session.execute(industry_stmt)).scalars().all()
        return sorted(b for b in brokers if b), sorted(i for i in industries if i)

    async def get_by_doc_type(
        self,
        doc_type: str,
        *,
        stock_code: str | None = None,
        q: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[NewsAnnouncement], int]:
        """Return paginated announcements filtered by doc_type."""
        return await self.list_paginated(
            stock_code=stock_code,
            doc_type=doc_type,
            q=q,
            offset=offset,
            limit=limit,
        )
