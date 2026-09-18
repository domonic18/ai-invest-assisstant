"""管理后台采集任务触发与日志 API 端点。"""

from datetime import date
from typing import Annotated, Any

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.pagination import DEFAULT_PAGE, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.core.exceptions import NotFoundError
from app.dependencies import get_current_admin_user, get_db
from app.schemas.collector import (
    CollectorDeadLetterResponse,
    CollectorLogResponse,
    CollectorLogSummaryResponse,
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
        raise NotFoundError(f"Unknown collector task: {task_name}")
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
                description=spec.description,
                data_type=spec.data_type,
                sources=list(spec.collectors),
                config_params=list(spec.config_params),
                run_params=list(spec.run_params),
                defaults=dict(spec.defaults),
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
        raise NotFoundError("Log not found")
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
    page: int = Query(DEFAULT_PAGE, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
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


@router.get("/logs/summary", response_model=CollectorLogSummaryResponse)
async def get_collector_log_summary(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CollectorLogSummaryResponse:
    """今日（Asia/Shanghai 日历日）采集日志按状态计数汇总。"""
    return await CollectorLogService(session).get_today_summary()


@router.get("/logs", response_model=PaginatedResponse)
async def list_collector_logs(
    session: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(DEFAULT_PAGE, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    task_name: str | None = None,
    source: str | None = None,
    status: str | None = None,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
) -> PaginatedResponse:
    """分页列出采集执行日志（开始时间倒序，可按任务键/渠道/状态/日期区间过滤）。"""
    total, rows = await CollectorLogService(session).list_recent(
        page,
        page_size,
        task_name=task_name,
        source=source,
        status=status,
        start_date=start_date,
        end_date=end_date,
    )
    items = [
        CollectorLogResponse.model_validate(row).model_dump(by_alias=True)
        for row in rows
    ]
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )


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
