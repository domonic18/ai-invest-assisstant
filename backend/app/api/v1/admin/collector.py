"""Admin collector trigger and log API endpoints."""

import asyncio
import traceback
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.dependencies import get_current_admin_user, get_db
from app.models.collector_log import CollectorLog
from app.schemas.collector import (
    CollectorLogResponse,
    CollectorRunResponse,
    CollectorTaskChannelItem,
    CollectorTaskChannelsResponse,
    CollectorTaskName,
    CollectorTaskRunRequest,
)
from collector.resolver import list_channels_for_task, resolve_channel_for_task

router = APIRouter(prefix="/collector", dependencies=[Depends(get_current_admin_user)])


_TASK_DATA_TYPE: dict[str, str] = {
    "kline": "kline_daily",
    "auction": "auction",
    "fund-flow": "fund_flow",
    "news": "news",
    "company-profile": "company_profile",
    "disclosure": "disclosure",
    "sector-fund-flow": "sector_fund_flow",
    "dragon-list": "dragon_list",
    "research-report": "research_report",
    "macro": "macro_indicator",
}


async def _run_collector_task(
    task_name: str,
    preferred_source: str | None,
    symbols: list[str] | None,
    period: str | None,
    start_date: str | None,
    end_date: str | None,
    sector_type: str | None,
    indicators: list[str] | None,
) -> None:
    """Run a collector task in the background and persist a log entry."""
    started_at = datetime.now(timezone.utc)
    log = CollectorLog(
        task_name=task_name,
        source="unknown",
        status="running",
        started_at=started_at,
        records_count=0,
        meta={},
    )
    async with AsyncSessionLocal() as session:
        session.add(log)
        await session.commit()
        await session.refresh(log)

    try:
        from collector.base import CollectResult
        from collector.tasks import TASK_MAP

        coro = cast(Callable[..., Any] | None, TASK_MAP.get(task_name))
        if coro is None:
            raise ValueError(f"Unknown collector task: {task_name}")

        kwargs: dict[str, Any] = {
            "preferred_source": preferred_source,
        }
        if symbols is not None:
            kwargs["symbols"] = symbols
        if task_name == "kline" and period:
            kwargs["period"] = period
        if task_name in {"disclosure", "dragon-list"}:
            if start_date:
                kwargs["start_date"] = start_date
            if end_date:
                kwargs["end_date"] = end_date
        if task_name == "sector-fund-flow" and sector_type:
            kwargs["sector_type"] = sector_type
        if task_name == "macro" and indicators:
            kwargs["indicators"] = indicators

        result: CollectResult = await coro(**kwargs)
    except Exception as exc:  # noqa: BLE001
        finished_at = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as session:
            log.status = "failed"
            log.finished_at = finished_at
            log.error_msg = f"{exc!r}\n{traceback.format_exc()}"
            await session.merge(log)
            await session.commit()
        return

    async with AsyncSessionLocal() as session:
        log.status = result.status.value
        log.source = result.source
        log.finished_at = result.finished_at
        log.records_count = result.items_stored
        log.error_msg = "\n".join(result.errors) if result.errors else None
        log.meta = result.metadata or {}
        await session.merge(log)
        await session.commit()


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
    body: CollectorTaskRunRequest | None = None,
) -> CollectorRunResponse:
    """Trigger a collector task asynchronously.

    The task runs in the background; use the log endpoint to monitor progress.
    An optional body allows overriding the resolved channel and passing symbols.
    """
    preferred_source = body.preferred_source if body else None
    symbols = body.symbols if body else None
    period = body.period if body else None
    start_date = body.start_date if body else None
    end_date = body.end_date if body else None
    sector_type = body.sector_type if body else None
    indicators = body.indicators if body else None
    asyncio.create_task(
        _run_collector_task(
            task_name.value,
            preferred_source=preferred_source,
            symbols=symbols,
            period=period,
            start_date=start_date,
            end_date=end_date,
            sector_type=sector_type,
            indicators=indicators,
        )
    )
    return CollectorRunResponse(task_name=task_name.value)


@router.get("/logs", response_model=list[CollectorLogResponse])
async def list_collector_logs(
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
) -> list[CollectorLogResponse]:
    """List recent collector execution logs, newest first."""
    if limit <= 0 or limit > 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="limit must be between 1 and 200",
        )
    stmt = select(CollectorLog).order_by(desc(CollectorLog.started_at)).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return [CollectorLogResponse.model_validate(row) for row in rows]
