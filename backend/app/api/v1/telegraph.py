"""财联社电报 API 路由。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.pagination import DEFAULT_PAGE, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.stock import PaginatedResponse
from app.services.market import telegraph_service

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
async def list_telegraph(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(DEFAULT_PAGE, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    category: str | None = Query(None, description="分类精确筛选"),
    min_importance: int | None = Query(None, ge=1, description="重要度下限"),
    min_ai_score: int | None = Query(
        None, ge=0, le=100, description="AI 重要度下限（仅含已分级条目）"
    ),
    subscription_only: bool = Query(False, description="仅看订阅命中条目"),
) -> PaginatedResponse:
    """分页查询电报，按 publish_time 降序，附 AI 分级/评分构成/订阅命中。"""
    rows, total = await telegraph_service.list_telegraph(
        session,
        page=page,
        page_size=page_size,
        category=category,
        min_importance=min_importance,
        min_ai_score=min_ai_score,
        subscription_only=subscription_only,
        user_id=current_user.id,
    )
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=await telegraph_service.enrich_and_respond(
            session, rows, user_id=current_user.id
        ),
    )
