"""财联社电报 API 路由。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.stock import PaginatedResponse
from app.schemas.telegraph import TelegraphResponse
from app.services.market import telegraph_service

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
async def list_telegraph(
    session: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: str | None = Query(None, description="分类精确筛选"),
    min_importance: int | None = Query(None, ge=1, description="重要度下限"),
) -> PaginatedResponse:
    """分页查询电报，按 publish_time 降序。"""
    items, total = await telegraph_service.list_telegraph(
        session,
        page=page,
        page_size=page_size,
        category=category,
        min_importance=min_importance,
    )
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[TelegraphResponse.model_validate(item) for item in items],
    )
