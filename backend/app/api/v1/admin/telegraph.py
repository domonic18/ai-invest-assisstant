"""管理后台电报（财联社）查删管理 API 端点。"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.pagination import DEFAULT_PAGE, DEFAULT_PAGE_SIZE
from app.dependencies import get_current_admin_user, get_db
from app.schemas.base import BatchDeleteRequest
from app.schemas.stock import PaginatedResponse
from app.schemas.telegraph import AdminTelegraphResponse
from app.services.admin.telegraph import AdminTelegraphService

router = APIRouter(dependencies=[Depends(get_current_admin_user)])


@router.get("/", response_model=PaginatedResponse)
async def list_telegraph(
    session: Annotated[AsyncSession, Depends(get_db)],
    q: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = DEFAULT_PAGE,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> PaginatedResponse:
    """分页查询电报（关键词/发布日期区间，publish_time 降序，含 AI 分级）。"""
    rows, total = await AdminTelegraphService(session).list_telegraph(
        q=q, start_date=start_date, end_date=end_date, page=page, page_size=page_size
    )
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[
            AdminTelegraphResponse(
                id=row.id,
                title=row.title,
                content=row.content,
                category=row.category,
                importance=row.importance,
                stock_codes=row.stock_codes,
                publish_time=row.publish_time,
                ai_score=score,
                ai_scored_at=scored_at,
            )
            for row, score, scored_at in rows
        ],
    )


@router.post("/batch-delete", status_code=status.HTTP_200_OK)
async def batch_delete_telegraph(
    data: BatchDeleteRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, int]:
    """批量删除电报，返回删除条数。"""
    deleted = await AdminTelegraphService(session).delete_telegraph_batch(data.ids)
    return {"deleted": deleted}


@router.delete("/{telegraph_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_telegraph(
    telegraph_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """删除单条电报。"""
    await AdminTelegraphService(session).delete_telegraph(telegraph_id)
