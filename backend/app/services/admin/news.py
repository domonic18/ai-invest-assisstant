"""Admin news announcement business services."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news_announcement import NewsAnnouncement
from app.repositories.reports.news_announcement_repository import NewsAnnouncementRepository
from app.schemas.news_announcement import (
    NewsAnnouncementCreate,
    NewsAnnouncementResponse,
    NewsAnnouncementUpdate,
)


class AdminNewsService:
    """后台新闻公告管理服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = NewsAnnouncementRepository(session)

    async def list_news(
        self,
        stock_code: str | None = None,
        doc_type: str | None = None,
        q: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[NewsAnnouncement], int]:
        """分页查询新闻公告列表。"""
        offset = (page - 1) * page_size
        return await self.repo.list_paginated(
            stock_code=stock_code,
            doc_type=doc_type,
            q=q,
            offset=offset,
            limit=page_size,
        )

    async def get_news(self, news_id: int) -> NewsAnnouncement | None:
        """按 ID 查询新闻公告。"""
        return await self.repo.get(news_id)

    async def create_news(self, data: NewsAnnouncementCreate) -> NewsAnnouncement:
        """创建新闻公告。"""
        news = NewsAnnouncement(
            stock_code=data.stock_code,
            doc_type=data.doc_type,
            title=data.title,
            summary=data.summary,
            content=data.content,
            source=data.source,
            source_url=data.source_url,
            publish_date=data.publish_date,
            sentiment=data.sentiment,
            keywords=data.keywords,
            industry_tags=data.industry_tags,
            elasticsearch_doc_id=data.elasticsearch_doc_id,
            extra=data.extra,
        )
        self.repo.add(news)
        await self.session.commit()
        await self.repo.refresh(news)
        return news

    async def update_news(
        self, news_id: int, data: NewsAnnouncementUpdate
    ) -> NewsAnnouncement | None:
        """更新新闻公告。"""
        news = await self.repo.get(news_id)
        if not news:
            return None

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(news, field, value)

        await self.session.commit()
        await self.repo.refresh(news)
        return news

    async def delete_news(self, news_id: int) -> None:
        """删除新闻公告。"""
        news = await self.repo.get(news_id)
        if not news:
            raise ValueError(f"News {news_id} not found")
        await self.repo.delete(news)
        await self.session.commit()

    def _to_response(self, news: NewsAnnouncement) -> NewsAnnouncementResponse:
        """序列化为新闻公告响应模型。"""
        return NewsAnnouncementResponse.model_validate(news)
