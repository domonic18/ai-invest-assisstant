"""后台新闻公告业务服务。"""

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.news_document import NewsDocument
from app.repositories.reports.news_document_repository import NewsDocumentRepository
from app.schemas.news_document import (
    NewsDocumentCreate,
    NewsDocumentResponse,
    NewsDocumentUpdate,
)
from app.services.news.news_channel_service import (
    is_flash_news_visible,
    set_flash_news_visible,
)


class AdminNewsService:
    """后台新闻公告管理服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = NewsDocumentRepository(session)

    async def list_news(
        self,
        stock_code: str | None = None,
        doc_type: str | None = None,
        q: str | None = None,
        source: str | None = None,
        broker: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[NewsDocument], int]:
        """分页查询新闻公告列表。"""
        offset = (page - 1) * page_size
        return await self.repo.list_paginated(
            stock_code=stock_code,
            doc_type=doc_type,
            source=source,
            q=q,
            broker=broker,
            start_date=start_date,
            end_date=end_date,
            order_by=NewsDocument.publish_date.desc().nullslast(),
            offset=offset,
            limit=page_size,
        )

    async def get_news(self, news_id: int) -> NewsDocument:
        """按 ID 查询新闻公告，缺失时抛 NotFoundError。"""
        news = await self.repo.get(news_id)
        if not news:
            raise NotFoundError(f"News {news_id} not found")
        return news

    async def create_news(self, data: NewsDocumentCreate) -> NewsDocument:
        """创建新闻公告。"""
        news = NewsDocument(
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
            extra=data.extra,
        )
        self.repo.add(news)
        await self.session.commit()
        await self.repo.refresh(news)
        return news

    async def update_news(
        self, news_id: int, data: NewsDocumentUpdate
    ) -> NewsDocument:
        """更新新闻公告，缺失时抛 NotFoundError。"""
        news = await self.get_news(news_id)

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(news, field, value)

        await self.session.commit()
        await self.repo.refresh(news)
        return news

    async def delete_news(self, news_id: int) -> None:
        """删除新闻公告。"""
        news = await self.get_news(news_id)
        await self.repo.delete(news)
        await self.session.commit()

    async def delete_news_batch(self, ids: list[int]) -> int:
        """批量删除新闻公告，返回删除条数。"""
        deleted = await self.repo.delete_by_ids(ids)
        await self.session.commit()
        return deleted

    async def get_flash_news_display(self) -> bool:
        """东财快讯资讯中心展示开关状态（缺省展示）。"""
        return await is_flash_news_visible(self.session)

    async def set_flash_news_display(self, visible: bool) -> bool:
        """写入东财快讯展示开关；采集启停归「采集管理」，此处不触碰任务状态。"""
        return await set_flash_news_visible(self.session, visible)

    def _to_response(self, news: NewsDocument) -> NewsDocumentResponse:
        """序列化为新闻公告响应模型。"""
        return NewsDocumentResponse.model_validate(news)
