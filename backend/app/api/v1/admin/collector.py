"""管理后台采集任务触发与日志 API 端点。"""

from typing import Annotated, Any

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin_user, get_db
from app.schemas.collector import (
    CollectorDeadLetterResponse,
    CollectorLogResponse,
    CollectorRunResponse,
    CollectorTaskCatalogItem,
    CollectorTaskCatalogResponse,
    CollectorTaskChannelItem,
    CollectorTaskChannelsResponse,
    CollectorTaskRunRequest,
)
from app.schemas.stock import PaginatedResponse
from app.services.collector.collector_log_service import CollectorLogService
from collector.celery_app import app as celery_app
from collector.runtime.dispatcher import dispatch_collector_task
from collector.runtime.registry import TASK_SPECS, TaskSpec
from collector.runtime.resolver import list_channels_for_task, resolve_channel_for_task

router = APIRouter(prefix="/collector", dependencies=[Depends(get_current_admin_user)])


def _get_task_spec_or_404(task_name: str) -> TaskSpec:
    """任务名校验唯一入口：未注册的任务返回 404。"""
    spec = TASK_SPECS.get(task_name)
    if spec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown collector task: {task_name}",
        )
    return spec


# 注意：本路由必须声明在 /tasks/{task_name}/* 参数路由之前，避免 "catalog" 被吞。
@router.get("/tasks/catalog", response_model=CollectorTaskCatalogResponse)
async def get_collector_task_catalog() -> CollectorTaskCatalogResponse:
    """返回全部已注册采集任务的元数据目录（UI 触发列表唯一数据源）。"""
    return CollectorTaskCatalogResponse(
        items=[
            CollectorTaskCatalogItem(
                name=spec.name,
                label=spec.label,
                data_type=spec.data_type,
                sources=list(spec.collectors),
                config_params=list(spec.config_params),
                run_params=list(spec.run_params),
            )
            for spec in TASK_SPECS.values()
        ]
    )


@router.post("/tasks/{task_name}/run", response_model=CollectorRunResponse)
async def run_collector_task(
    task_name: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    body: CollectorTaskRunRequest | None = None,
) -> CollectorRunResponse:
    """将采集任务派发到 collector worker 队列。

    任务由 collector worker 执行，而非 web 容器；
    通过日志端点监控进度。
    """
    spec = _get_task_spec_or_404(task_name)
    params = body.model_dump(exclude_unset=True) if body else {}
    log = await dispatch_collector_task(
        session=session,
        task_name=spec.name,
        params=params,
    )
    return CollectorRunResponse(
        task_name=spec.name,
        status="dispatched",
        log_id=log.id,
        celery_task_id=log.celery_task_id,
    )


@router.get("/logs/{log_id}/celery-status")
async def get_collector_log_celery_status(
    log_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """返回采集日志对应的 Celery 任务状态。"""
    log = await CollectorLogService(session).get_by_id(log_id)
    if log is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Log not found",
        )
    if not log.celery_task_id:
        return {
            "log_id": log_id,
            "celery_state": None,
            "collector_status": log.status,
        }
    result = AsyncResult(log.celery_task_id, app=celery_app)
    return {
        "log_id": log_id,
        "celery_task_id": log.celery_task_id,
        "celery_state": result.state,
        "collector_status": log.status,
    }


@router.get("/dead-letters", response_model=PaginatedResponse)
async def list_dead_letters(
    session: Annotated[AsyncSession, Depends(get_db)],
    page: int = 1,
    page_size: int = 20,
) -> PaginatedResponse:
    """按最新优先列出采集死信记录。"""
    total, rows = await CollectorLogService(session).list_dead_letters(page, page_size)
    items = [
        CollectorDeadLetterResponse.model_validate(row).model_dump() for row in rows
    ]
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )


@router.get("/logs", response_model=list[CollectorLogResponse])
async def list_collector_logs(
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
) -> list[CollectorLogResponse]:
    """按最新优先列出最近的采集执行日志。"""
    try:
        rows = await CollectorLogService(session).list_recent(limit)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return [CollectorLogResponse.model_validate(row) for row in rows]


@router.get(
    "/tasks/{task_name}/channels",
    response_model=CollectorTaskChannelsResponse,
)
async def get_collector_task_channels(
    task_name: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CollectorTaskChannelsResponse:
    """列出任务可用的渠道以及实际将使用的渠道。"""
    spec = _get_task_spec_or_404(task_name)
    channels = await list_channels_for_task(session, spec.name)
    resolved = await resolve_channel_for_task(session, spec.name)
    return CollectorTaskChannelsResponse(
        task_name=spec.name,
        data_type=spec.data_type,
        channels=[CollectorTaskChannelItem.model_validate(ch) for ch in channels],
        resolved_source=resolved.source if resolved else None,
    )
