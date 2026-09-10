"""东财快讯查询服务（基础流：无 AI 分级/订阅命中）。"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news_document import NewsDocument
from app.repositories.reports.news_document_repository import NewsDocumentRepository
from app.schemas.news import NewsFlashItemResponse

_FLASH_SOURCE = "eastmoney"


def _to_response(item: NewsDocument) -> NewsFlashItemResponse:
    # 快讯条目 publish_date 由采集器 validate/required_fields 保证非空
    publish_date = item.publish_date
    assert publish_date is not None
    return NewsFlashItemResponse(
        id=item.id,
        source=item.source or _FLASH_SOURCE,
        title=item.title,
        summary=item.summary,
        content=item.content,
        source_url=item.source_url,
        publish_time=publish_date,
    )


async def list_flash_news(
    session: AsyncSession,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[NewsFlashItemResponse], int]:
    """分页查询东财快讯（publish_date 降序）。"""
    repo = NewsDocumentRepository(session)
    rows, total = await repo.list_paginated(
        doc_type="news",
        source=_FLASH_SOURCE,
        order_by=NewsDocument.publish_date.desc(),
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    return [_to_response(row) for row in rows], total
