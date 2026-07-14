"""Admin news announcement business services."""


from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news_announcement import NewsAnnouncement
from app.schemas.news_announcement import (
    NewsAnnouncementCreate,
    NewsAnnouncementResponse,
    NewsAnnouncementUpdate,
)


class AdminNewsService:
    """后台新闻公告管理服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_news(
        self,
        stock_code: str | None = None,
        doc_type: str | None = None,
        q: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[NewsAnnouncement], int]:
        """分页查询新闻公告列表。"""
        stmt = select(NewsAnnouncement).order_by(NewsAnnouncement.created_at.desc())
        count_stmt = select(func.count()).select_from(NewsAnnouncement)

        if stock_code:
            stmt = stmt.where(NewsAnnouncement.stock_code == stock_code)
            count_stmt = count_stmt.where(NewsAnnouncement.stock_code == stock_code)
        if doc_type:
            stmt = stmt.where(NewsAnnouncement.doc_type == doc_type)
            count_stmt = count_stmt.where(NewsAnnouncement.doc_type == doc_type)
        if q:
            pattern = f"%{q}%"
            stmt = stmt.where(
                NewsAnnouncement.title.ilike(pattern)
                | NewsAnnouncement.content.ilike(pattern)
            )
            count_stmt = count_stmt.where(
                NewsAnnouncement.title.ilike(pattern)
                | NewsAnnouncement.content.ilike(pattern)
            )

        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        total = await self.session.scalar(count_stmt) or 0
        return list(result.scalars().all()), total

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
            es_id=data.es_id,
            extra=data.extra,
        )
        self.session.add(news)
        await self.session.flush()
        await self.session.refresh(news)
        return news

    async def update_news(
        self, news_id: int, data: NewsAnnouncementUpdate
    ) -> NewsAnnouncement | None:
        """更新新闻公告。"""
        news = await self.session.get(NewsAnnouncement, news_id)
        if not news:
            return None

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(news, field, value)

        await self.session.flush()
        await self.session.refresh(news)
        return news

    async def delete_news(self, news_id: int) -> None:
        """删除新闻公告。"""
        news = await self.session.get(NewsAnnouncement, news_id)
        if not news:
            raise ValueError(f"News {news_id} not found")
        await self.session.delete(news)
        await self.session.flush()

    def _to_response(self, news: NewsAnnouncement) -> NewsAnnouncementResponse:
        """序列化为新闻公告响应模型。"""
        return NewsAnnouncementResponse.model_validate(news)
