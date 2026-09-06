"""管理后台采集任务管理 API 端点。"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.pagination import DEFAULT_PAGE, DEFAULT_PAGE_SIZE
from app.dependencies import get_current_admin_user, get_db
from app.schemas.collector_task import (
    CollectorTaskCreate,
    CollectorTaskResponse,
    CollectorTaskUpdate,
)
from app.schemas.stock import PaginatedResponse
from app.services.admin.tasks import AdminTaskService

router = APIRouter(dependencies=[Depends(get_current_admin_user)])


@router.get("/", response_model=PaginatedResponse)
async def list_tasks(
    session: Annotated[AsyncSession, Depends(get_db)],
    page: int = DEFAULT_PAGE,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> PaginatedResponse:
    """查询采集任务列表。"""
    items, total = await AdminTaskService(session).list_tasks(page, page_size)
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[CollectorTaskResponse.model_validate(item) for item in items],
    )


@router.post(
    "/",
    response_model=CollectorTaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_task(
    data: CollectorTaskCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CollectorTaskResponse:
    """创建采集任务。"""
    task = await AdminTaskService(session).create_task(data)
    return CollectorTaskResponse.model_validate(task)


@router.get("/{task_id}", response_model=CollectorTaskResponse)
async def get_task(
    task_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CollectorTaskResponse:
    """获取单个采集任务。"""
    task = await AdminTaskService(session).get_task(task_id)
    return CollectorTaskResponse.model_validate(task)


@router.put("/{task_id}", response_model=CollectorTaskResponse)
async def update_task(
    task_id: int,
    data: CollectorTaskUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CollectorTaskResponse:
    """更新采集任务。"""
    task = await AdminTaskService(session).update_task(task_id, data)
    return CollectorTaskResponse.model_validate(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """删除采集任务。"""
    await AdminTaskService(session).delete_task(task_id)


@router.post("/{task_id}/pause", response_model=CollectorTaskResponse)
async def pause_task(
    task_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CollectorTaskResponse:
    """暂停采集任务。"""
    task = await AdminTaskService(session).pause_task(task_id)
    return CollectorTaskResponse.model_validate(task)


@router.post("/{task_id}/resume", response_model=CollectorTaskResponse)
async def resume_task(
    task_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CollectorTaskResponse:
    """恢复采集任务。"""
    task = await AdminTaskService(session).resume_task(task_id)
    return CollectorTaskResponse.model_validate(task)


@router.post("/{task_id}/trigger", response_model=CollectorTaskResponse)
async def trigger_task(
    task_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CollectorTaskResponse:
    """触发采集任务并将其派发到采集器队列。"""
    task = await AdminTaskService(session).trigger_task(task_id)
    return CollectorTaskResponse.model_validate(task)
