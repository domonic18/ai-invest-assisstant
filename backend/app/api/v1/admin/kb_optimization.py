"""管理后台技能优化建议端点（批次 H2/H3，arch/12 §9）。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.pagination import DEFAULT_PAGE, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.dependencies import get_current_admin_user, get_db
from app.models.user import User
from app.schemas.kb import (
    KbOptimizationCreateRequest,
    KbOptimizationListResponse,
    KbOptimizationReviewRequest,
    KbOptimizationSuggestionResponse,
)
from app.services.kb import optimization_service

router = APIRouter(prefix="/kb", dependencies=[Depends(get_current_admin_user)])


@router.get(
    "/optimization-suggestions", response_model=KbOptimizationListResponse
)
async def list_suggestions(
    session: Annotated[AsyncSession, Depends(get_db)],
    status_filter: str | None = Query(
        default=None, alias="status", description="状态过滤"
    ),
    page: int = Query(default=DEFAULT_PAGE, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> KbOptimizationListResponse:
    """建议单分页清单（created_at 倒序）。"""
    rows, total = await optimization_service.list_suggestions(
        session, status=status_filter, page=page, page_size=page_size
    )
    return KbOptimizationListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[KbOptimizationSuggestionResponse.model_validate(r) for r in rows],
    )


@router.post(
    "/optimization-suggestions",
    response_model=KbOptimizationSuggestionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_suggestion(
    data: KbOptimizationCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_admin_user)],
) -> KbOptimizationSuggestionResponse:
    """发起建议单生成（目标技能 × 知识源；同技能未处理单禁止新发）。"""
    row = await optimization_service.create_suggestion(
        session,
        skill_id=data.skill_id,
        source_id=data.source_id,
        actor_id=user.id,
    )
    return KbOptimizationSuggestionResponse.model_validate(row)


@router.get(
    "/optimization-suggestions/{suggestion_id}",
    response_model=KbOptimizationSuggestionResponse,
)
async def get_suggestion(
    suggestion_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> KbOptimizationSuggestionResponse:
    """建议单详情（含生成产物与审核留档）。"""
    row = await optimization_service.get_suggestion(session, suggestion_id)
    return KbOptimizationSuggestionResponse.model_validate(row)


@router.post(
    "/optimization-suggestions/{suggestion_id}/review",
    response_model=KbOptimizationSuggestionResponse,
)
async def review_suggestion(
    suggestion_id: int,
    data: KbOptimizationReviewRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_admin_user)],
) -> KbOptimizationSuggestionResponse:
    """审核建议单：apply（可带 revisions 修订后应用）/ reject（note 必填）。"""
    row = await optimization_service.review_suggestion(
        session,
        suggestion_id,
        action=data.action,
        note=data.note,
        revisions={r.index: r.suggested_text for r in data.revisions},
        actor_id=user.id,
    )
    return KbOptimizationSuggestionResponse.model_validate(row)
