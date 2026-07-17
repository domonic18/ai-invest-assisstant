"""Dispatcher for collector tasks from the web API to the collector worker.

The dispatcher creates a pending ``CollectorLog`` row, pushes the task payload
onto the Redis queue, and returns the log ID so callers can track execution.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collector_log import CollectorLog
from collector.queue import CollectorQueue


async def dispatch_collector_task(
    session: AsyncSession,
    task_name: str,
    params: dict[str, Any],
    queue_key: str | None = None,
) -> CollectorLog:
    """Create a pending log entry and push the task to the Redis queue.

    Args:
        session: Database session for persisting the log entry.
        task_name: The collector task name (e.g. ``financial-report``).
        params: Task parameters such as ``symbols``, ``start_date``, etc.
        queue_key: Optional override for the Redis queue key.

    Returns:
        The newly created ``CollectorLog`` row.
    """
    log = CollectorLog(
        task_name=task_name,
        source=params.get("preferred_source") or "unknown",
        status="pending",
        started_at=datetime.now(timezone.utc),
        records_count=0,
        meta=params,
    )
    session.add(log)
    await session.flush()
    await session.refresh(log)

    payload = {"task": task_name, "log_id": log.id, **params}
    queue = CollectorQueue(queue_key=queue_key)
    try:
        await queue.push(payload)
    except Exception as exc:  # noqa: BLE001
        await queue.close()
        log.status = "failed"
        log.error_msg = f"Failed to push task to collector queue: {exc}"
        log.finished_at = datetime.now(timezone.utc)
        await session.flush()
        raise
    finally:
        await session.flush()

    return log
