"""Admin news announcement management API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin_user, get_db
from app.schemas.news_announcement import (
    NewsAnnouncementCreate,
    NewsAnnouncementResponse,
    NewsAnnouncementUpdate,
)
from app.schemas.stock import PaginatedResponse
from app.services.admin_news_service import AdminNewsService

router = APIRouter(dependencies=[Depends(get_current_admin_user)])


@router.get("/", response_model=PaginatedResponse)
async def list_news(
    session: Annotated[AsyncSession, Depends(get_db)],
    stock_code: str | None = None,
    doc_type: str | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> PaginatedResponse:
    """查询新闻公告列表。"""
    items, total = await AdminNewsService(session).list_news(
        stock_code, doc_type, q, page, page_size
    )
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[NewsAnnouncementResponse.model_validate(item) for item in items],
    )


@router.post(
    "/",
    response_model=NewsAnnouncementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_news(
    data: NewsAnnouncementCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> NewsAnnouncementResponse:
    """创建新闻公告。"""
    news = await AdminNewsService(session).create_news(data)
    return NewsAnnouncementResponse.model_validate(news)


@router.get("/{news_id}", response_model=NewsAnnouncementResponse)
async def get_news(
    news_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> NewsAnnouncementResponse:
    """获取单条新闻公告。"""
    news = await AdminNewsService(session).get_news(news_id)
    if not news:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="News not found",
        )
    return NewsAnnouncementResponse.model_validate(news)


@router.put("/{news_id}", response_model=NewsAnnouncementResponse)
async def update_news(
    news_id: int,
    data: NewsAnnouncementUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> NewsAnnouncementResponse:
    """更新新闻公告。"""
    news = await AdminNewsService(session).update_news(news_id, data)
    if not news:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="News not found",
        )
    return NewsAnnouncementResponse.model_validate(news)


@router.delete("/{news_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_news(
    news_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """删除新闻公告。"""
    try:
        await AdminNewsService(session).delete_news(news_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
