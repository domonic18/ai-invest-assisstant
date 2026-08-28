"""把采集任务从 web API 分发到 Celery 的调度器。

dispatcher 创建一条 pending 状态的 ``CollectorLog`` 行，并通过
``run_collector_task.apply_async`` 把任务提交给 Celery。
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.collector import CollectorStatus
from app.models.collector_log import CollectorLog
from collector.celery_app import resolve_task_options


async def dispatch_collector_task(
    session: AsyncSession,
    task_name: str,
    params: dict[str, Any],
) -> CollectorLog:
    """创建 pending 日志条目并把任务提交到 Celery。

    Args:
        session: 用于持久化日志条目的数据库会话。
        task_name: 采集任务名（如 ``financial-report``）。
        params: 任务参数，如 ``symbols``、``start_date`` 等。

    Returns:
        新创建的 ``CollectorLog`` 行。
    """
    from collector.celery_tasks import run_collector_task

    log = CollectorLog(
        task_name=task_name,
        source=params.get("preferred_source") or "unknown",
        status=CollectorStatus.PENDING,
        started_at=datetime.now(timezone.utc),
        records_count=0,
        meta=_serialize_meta(params),
    )
    session.add(log)
    await session.flush()
    await session.refresh(log)

    payload = {"task": task_name, "log_id": log.id, **params}

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
    """返回 ``collector_task`` 上存储的队列覆盖值（如有）。"""
    from sqlalchemy import select

    from app.models.collector_task import CollectorTask

    task = await session.scalar(
        select(CollectorTask.queue).where(CollectorTask.task_name == task_name)
    )
    return task


def _serialize_meta(params: dict[str, Any]) -> dict[str, Any]:
    """返回分发参数的 JSON 安全副本，用于 CollectorLog.meta。"""
    meta: dict[str, Any] = {}
    for key, value in params.items():
        if isinstance(value, (list, dict, str, int, float, bool)) or value is None:
            meta[key] = value
        else:
            meta[key] = str(value)
    return meta
