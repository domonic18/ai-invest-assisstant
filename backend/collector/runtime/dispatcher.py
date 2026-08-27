"""Dispatcher for collector tasks from the web API to the collector worker.

The dispatcher creates a pending ``CollectorLog`` row and submits the task to
Celery.  A legacy Redis-list code path remains available behind the
``COLLECTOR_USE_LEGACY_QUEUE`` flag for rollback during the migration.
"""

import os
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collector_log import CollectorLog
from collector.celery_app import resolve_task_options
from collector.core.config import collector_queue_key
from collector.runtime.queue import CollectorQueue

_USE_LEGACY_QUEUE = os.getenv("COLLECTOR_USE_LEGACY_QUEUE", "false").lower() == "true"


async def dispatch_collector_task(
    session: AsyncSession,
    task_name: str,
    params: dict[str, Any],
    queue_key: str | None = None,
) -> CollectorLog:
    """Create a pending log entry and submit the task to Celery (or legacy queue).

    Args:
        session: Database session for persisting the log entry.
        task_name: The collector task name (e.g. ``financial-report``).
        params: Task parameters such as ``symbols``, ``start_date``, etc.
        queue_key: Optional override for the legacy Redis queue key.

    Returns:
        The newly created ``CollectorLog`` row.
    """
    from collector.celery_tasks import run_collector_task

    log = CollectorLog(
        task_name=task_name,
        source=params.get("preferred_source") or "unknown",
        status="pending",
        started_at=datetime.now(timezone.utc),
        records_count=0,
        meta=_serialize_meta(params),
    )
    session.add(log)
    await session.flush()
    await session.refresh(log)

    payload = {"task": task_name, "log_id": log.id, **params}

    if _USE_LEGACY_QUEUE:
        await _push_legacy(payload, queue_key, log, session)
    else:
        queue_override = await _load_task_queue(session, task_name)
        options = resolve_task_options(
            task_name,
            params.get("preferred_source"),
            queue_override=queue_override,
        )
        result = run_collector_task.apply_async(args=[payload], **options)
        log.celery_task_id = result.id
        await session.commit()

    return log


async def _load_task_queue(session: AsyncSession, task_name: str) -> str | None:
    """Return the queue override stored on ``collector_task`` if any."""
    from sqlalchemy import select

    from app.models.collector_task import CollectorTask

    task = await session.scalar(
        select(CollectorTask.queue).where(CollectorTask.task_name == task_name)
    )
    return task


def _serialize_meta(params: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-safe copy of dispatch params for CollectorLog.meta."""
    meta: dict[str, Any] = {}
    for key, value in params.items():
        if isinstance(value, (list, dict, str, int, float, bool)) or value is None:
            meta[key] = value
        else:
            meta[key] = str(value)
    return meta


async def _push_legacy(
    payload: dict[str, Any],
    queue_key: str | None,
    log: CollectorLog,
    session: AsyncSession,
) -> None:
    """Push the task to the legacy Redis list and commit the log row."""
    queue = CollectorQueue(queue_key=queue_key or collector_queue_key)
    try:
        await queue.push(payload)
    except Exception as exc:  # noqa: BLE001
        await queue.close()
        log.status = "failed"
        log.error_msg = f"Failed to push task to collector queue: {exc}"
        log.finished_at = datetime.now(timezone.utc)
        await session.commit()
        raise
    finally:
        await session.commit()
