"""Admin collector trigger and log API endpoints."""

from typing import Annotated, Any

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin_user, get_db
from app.models.collector_dead_letter import CollectorDeadLetter
from app.models.collector_log import CollectorLog
from app.schemas.collector import (
    CollectorLogResponse,
    CollectorRunResponse,
    CollectorTaskChannelItem,
    CollectorTaskChannelsResponse,
    CollectorTaskName,
    CollectorTaskRunRequest,
)
from app.schemas.stock import PaginatedResponse
from app.services.collector_log_service import CollectorLogService
from collector.celery_app import app as celery_app
from collector.runtime.dispatcher import dispatch_collector_task
from collector.runtime.registry import TASK_SPECS
from collector.runtime.resolver import list_channels_for_task, resolve_channel_for_task

router = APIRouter(prefix="/collector", dependencies=[Depends(get_current_admin_user)])


@router.post("/tasks/{task_name}/run", response_model=CollectorRunResponse)
async def run_collector_task(
    task_name: CollectorTaskName,
    session: Annotated[AsyncSession, Depends(get_db)],
    body: CollectorTaskRunRequest | None = None,
) -> CollectorRunResponse:
    """Dispatch a collector task to the collector worker queue.

    The task is executed by the collector workers, not the web container. Use
    the log endpoint to monitor progress.
    """
    params = body.model_dump(exclude_unset=True) if body else {}
    log = await dispatch_collector_task(
        session=session,
        task_name=task_name.value,
        params=params,
    )
    return CollectorRunResponse(
        task_name=task_name.value,
        status="dispatched",
        log_id=log.id,
        celery_task_id=log.celery_task_id,
    )


@router.get("/logs/{log_id}/celery-status")
async def get_collector_log_celery_status(
    log_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Return the Celery task state for a collector log entry."""
    log = await session.get(CollectorLog, log_id)
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
    """List collector dead-letter entries, newest first."""
    offset = (page - 1) * page_size
    total = await session.scalar(select(func.count(CollectorDeadLetter.id)))
    result = await session.execute(
        select(CollectorDeadLetter)
        .order_by(CollectorDeadLetter.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = result.scalars().all()
    items = []
    for row in rows:
        item = row.__dict__.copy()
        item.pop("_sa_instance_state", None)
        items.append(item)
    return PaginatedResponse(
        total=total or 0,
        page=page,
        page_size=page_size,
        items=items,
    )


@router.get("/logs", response_model=list[CollectorLogResponse])
async def list_collector_logs(
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
) -> list[CollectorLogResponse]:
    """List recent collector execution logs, newest first."""
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
    task_name: CollectorTaskName,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CollectorTaskChannelsResponse:
    """List channels available for a task and the channel that will be used."""
    channels = await list_channels_for_task(session, task_name.value)
    resolved = await resolve_channel_for_task(session, task_name.value)
    spec = TASK_SPECS.get(task_name.value)
    return CollectorTaskChannelsResponse(
        task_name=task_name.value,
        data_type=spec.data_type if spec is not None else task_name.value,
        channels=[CollectorTaskChannelItem.model_validate(ch) for ch in channels],
        resolved_source=resolved.source if resolved else None,
    )
