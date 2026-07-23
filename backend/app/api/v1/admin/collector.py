"""Admin collector trigger and log API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin_user, get_db
from app.schemas.collector import (
    CollectorLogResponse,
    CollectorRunResponse,
    CollectorTaskChannelItem,
    CollectorTaskChannelsResponse,
    CollectorTaskName,
    CollectorTaskRunRequest,
)
from app.services.collector_log_service import CollectorLogService
from collector.runtime.dispatcher import dispatch_collector_task
from collector.runtime.resolver import list_channels_for_task, resolve_channel_for_task

router = APIRouter(prefix="/collector", dependencies=[Depends(get_current_admin_user)])


_TASK_DATA_TYPE: dict[str, str] = {
    "kline": "quote_kline_stock_daily",
    "index-kline": "index_kline",
    "auction": "auction",
    "fund-flow": "fund_flow",
    "news": "news",
    "company-profile": "company_profile",
    "disclosure": "disclosure",
    "sector-fund-flow": "capital_fund_flow_sector",
    "dragon-list": "pool_dragon_tiger_stock",
    "research-report": "research_report",
    "financial-report": "financial_report",
    "ipo-info": "ipo_info",
    "fund-holdings": "fund_holding",
    "macro": "macro_indicator",
    "quote": "quote",
    "stock-list": "stock_list",
    "limit-up-pool": "pool_limit_up_stock",
}


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
    return CollectorTaskChannelsResponse(
        task_name=task_name.value,
        data_type=_TASK_DATA_TYPE.get(task_name.value, task_name.value),
        channels=[CollectorTaskChannelItem.model_validate(ch) for ch in channels],
        resolved_source=resolved.source if resolved else None,
    )


@router.post("/tasks/{task_name}/run", response_model=CollectorRunResponse)
async def run_collector_task(
    task_name: CollectorTaskName,
    session: Annotated[AsyncSession, Depends(get_db)],
    body: CollectorTaskRunRequest | None = None,
) -> CollectorRunResponse:
    """Dispatch a collector task to the collector worker queue.

    The task is executed by the collector container, not the web container. Use
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
