"""管理后台跟踪指数配置 API 端点。"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin_user, get_db
from app.schemas.tracked_index import (
    TrackedIndexCreate,
    TrackedIndexResponse,
    TrackedIndexToggleResponse,
    TrackedIndexUpdate,
)
from app.services.admin.tracked_index_service import TrackedIndexService

router = APIRouter(
    prefix="/tracked-indexes",
    dependencies=[Depends(get_current_admin_user)],
)


@router.get("", response_model=list[TrackedIndexResponse])
async def list_tracked_indexes(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[TrackedIndexResponse]:
    """列出全部跟踪指数配置（附最新行情）。"""
    return await TrackedIndexService(session).list_indexes()


@router.post("", response_model=TrackedIndexResponse, status_code=status.HTTP_201_CREATED)
async def create_tracked_index(
    data: TrackedIndexCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TrackedIndexResponse:
    """创建跟踪指数配置。"""
    return await TrackedIndexService(session).create_index(data)


@router.get("/{config_id}", response_model=TrackedIndexResponse)
async def get_tracked_index(
    config_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TrackedIndexResponse:
    """获取单条跟踪指数配置。"""
    return await TrackedIndexService(session).get_index(config_id)


@router.put("/{config_id}", response_model=TrackedIndexResponse)
async def update_tracked_index(
    config_id: int,
    data: TrackedIndexUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TrackedIndexResponse:
    """更新跟踪指数配置。"""
    return await TrackedIndexService(session).update_index(config_id, data)


@router.patch("/{config_id}/toggle", response_model=TrackedIndexToggleResponse)
async def toggle_tracked_index(
    config_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TrackedIndexToggleResponse:
    """切换启用状态（启用前校验数据源）。"""
    row = await TrackedIndexService(session).toggle_index(config_id)
    return TrackedIndexToggleResponse(id=row.id, is_enabled=row.is_enabled)


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tracked_index(
    config_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """删除跟踪指数配置。"""
    await TrackedIndexService(session).delete_index(config_id)
