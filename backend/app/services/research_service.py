"""Research report business services."""

from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news_announcement import NewsAnnouncement
from app.repositories.news_announcement_repository import NewsAnnouncementRepository


class ResearchService:
    """Research report business services."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = NewsAnnouncementRepository(session)

    async def list_reports(
        self,
        stock_code: str | None = None,
        q: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[NewsAnnouncement], int]:
        """分页查询研报列表。"""
        offset = (page - 1) * page_size
        return await self.repo.list_paginated(
            doc_type="research",
            stock_code=stock_code,
            q=q,
            start_date=start_date,
            end_date=end_date,
            order_by=NewsAnnouncement.publish_date.desc().nullslast(),
            offset=offset,
            limit=page_size,
        )

    async def get_report(self, report_id: int) -> NewsAnnouncement | None:
        """按 ID 查询研报详情。"""
        return await self.repo.get(report_id)

    async def summarize_report(self, report_id: int) -> dict[str, Any]:
        """获取研报摘要。"""
        report = await self.get_report(report_id)
        if report is None:
            raise ValueError(f"Research report {report_id} not found")

        if report.summary:
            return {"summary": report.summary}

        content = report.content or ""
        return {"summary": content[:500] if len(content) <= 500 else content[:500] + "..."}


# Module-level helpers for backwards compatibility.
async def list_reports(
    session: AsyncSession,
    stock_code: str | None = None,
    q: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[NewsAnnouncement], int]:
    return await ResearchService(session).list_reports(
        stock_code=stock_code,
        q=q,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )


async def get_report(session: AsyncSession, report_id: int) -> NewsAnnouncement | None:
    return await ResearchService(session).get_report(report_id)


async def summarize_report(session: AsyncSession, report_id: int) -> dict[str, Any]:
    return await ResearchService(session).summarize_report(report_id)
