"""管理后台新闻公告管理 API 端点。"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.pagination import DEFAULT_PAGE, DEFAULT_PAGE_SIZE
from app.dependencies import get_current_admin_user, get_db
from app.schemas.base import BatchDeleteRequest
from app.schemas.news_document import (
    NewsDocumentCreate,
    NewsDocumentResponse,
    NewsDocumentUpdate,
)
from app.schemas.stock import PaginatedResponse
from app.services.admin.news import AdminNewsService

router = APIRouter(dependencies=[Depends(get_current_admin_user)])


@router.get("/", response_model=PaginatedResponse)
async def list_news(
    session: Annotated[AsyncSession, Depends(get_db)],
    stock_code: str | None = None,
    doc_type: str | None = None,
    q: str | None = None,
    source: str | None = None,
    broker: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = DEFAULT_PAGE,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> PaginatedResponse:
    """查询新闻公告列表（关键词/来源/券商/发布日期区间，publish_date 降序）。"""
    items, total = await AdminNewsService(session).list_news(
        stock_code=stock_code,
        doc_type=doc_type,
        q=q,
        source=source,
        broker=broker,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[NewsDocumentResponse.model_validate(item) for item in items],
    )


@router.post("/batch-delete", status_code=status.HTTP_200_OK)
async def batch_delete_news(
    data: BatchDeleteRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, int]:
    """批量删除新闻公告，返回删除条数。"""
    deleted = await AdminNewsService(session).delete_news_batch(data.ids)
    return {"deleted": deleted}


@router.post(
    "/",
    response_model=NewsDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_news(
    data: NewsDocumentCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> NewsDocumentResponse:
    """创建新闻公告。"""
    news = await AdminNewsService(session).create_news(data)
    return NewsDocumentResponse.model_validate(news)


@router.get("/{news_id}", response_model=NewsDocumentResponse)
async def get_news(
    news_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> NewsDocumentResponse:
    """获取单条新闻公告。"""
    news = await AdminNewsService(session).get_news(news_id)
    return NewsDocumentResponse.model_validate(news)


@router.put("/{news_id}", response_model=NewsDocumentResponse)
async def update_news(
    news_id: int,
    data: NewsDocumentUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> NewsDocumentResponse:
    """更新新闻公告。"""
    news = await AdminNewsService(session).update_news(news_id, data)
    return NewsDocumentResponse.model_validate(news)


@router.delete("/{news_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_news(
    news_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """删除新闻公告。"""
    await AdminNewsService(session).delete_news(news_id)
