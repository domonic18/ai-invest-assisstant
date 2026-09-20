"""知识库消费侧 API（arch/12 §10.2）：权限 = admin 或 kb_settings 白名单。

E4 范围：混合检索 + 发布态章节树导航；播放凭证/代理流/书页/字幕留批次 F。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.kb import KbDocKind, KbPointType
from app.core.exceptions import ForbiddenError
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.kb import KbPublishedChaptersResponse, KbSearchResponse
from app.services.kb import search_service, settings_service


async def get_kb_authorized_user(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """知识库消费权限：admin 或 authorized_user_ids 白名单（arch/12 §9）。"""
    if user.role != "admin":
        settings = await settings_service.get_settings_row(session)
        if user.id not in (settings.authorized_user_ids or []):
            raise ForbiddenError("知识库访问未授权")
    return user


router = APIRouter(dependencies=[Depends(get_kb_authorized_user)])


@router.get("/search", response_model=KbSearchResponse)
async def search(
    session: Annotated[AsyncSession, Depends(get_db)],
    q: str = Query(..., min_length=1, max_length=200),
    source_id: int | None = Query(default=None),
    chapter_path: str | None = Query(default=None, max_length=600),
    point_type: KbPointType | None = Query(default=None),
    kind: KbDocKind | None = Query(default=None),
) -> KbSearchResponse:
    """混合检索：BM25 + 向量双路 RRF 融合，三类命中独立列表。"""
    return await search_service.search(
        session,
        q=q,
        source_id=source_id,
        chapter_path=chapter_path.split(",") if chapter_path else None,
        point_type=point_type.value if point_type else None,
        kind=kind.value if kind else None,
    )


@router.get(
    "/sources/{source_id}/chapters", response_model=KbPublishedChaptersResponse
)
async def get_chapters(
    source_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> KbPublishedChaptersResponse:
    """发布态章节树导航（消费侧不暴露 draft）。"""
    return await search_service.get_published_chapters(session, source_id)
