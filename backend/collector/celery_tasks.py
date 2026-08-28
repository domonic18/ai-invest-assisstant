"""Celery task wrappers for collector execution.

This module exposes a single generic Celery task that executes any collector
spider registered in ``collector.runtime.registry.TASK_MAP``.  The task body
reuses ``collector.runtime.runner.run_task`` so that logging, status
persistence, and source fallback remain unchanged.
"""

import asyncio
import traceback
from datetime import datetime, timezone
from typing import Any

import structlog
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import select

from app.constants.collector import CollectorStatus
from app.core.database import AsyncSessionLocal
from app.models.collector_dead_letter import CollectorDeadLetter
from app.models.collector_log import CollectorLog
from app.models.collector_task import CollectorTask
from collector.celery_app import app
from collector.core.base import CollectResult
from collector.core.logging import configure_logging
from collector.runtime.runner import run_task

logger = structlog.get_logger(__name__)

_ERROR_MSG_MAX_LEN = 4000


def _truncate(text: str) -> str:
    return text[:_ERROR_MSG_MAX_LEN]


class AsyncTask(Task):
    """Celery task base that runs async code on a persistent child-process loop.

    Celery prefork children reuse the same process for many tasks.  The default
    ``asyncio.run()`` pattern creates and destroys an event loop for every task,
    which leaves asyncpg connections from the previous loop in the SQLAlchemy
    pool; the next task then reuses those connections on a new loop and gets
    ``asyncpg.exceptions.InterfaceError: another operation is in progress``.

    Keeping one loop per child process eliminates that cross-loop connection
    reuse and lets the connection pool warm up normally.
    """

    _loop: asyncio.AbstractEventLoop | None = None

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        """Return the child-process event loop, creating it if necessary."""
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop


class LogAwareTask(AsyncTask):
    """Base Celery task that writes timeout status before a hard kill."""

    def on_failure(
        self,
        exc: BaseException,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        einfo: Any,
    ) -> None:
        """Called when all retries are exhausted or failure is permanent."""
        try:
            payload = args[0] if args else {}
            log_id = payload.get("log_id")
            task_name = payload.get("task", "unknown")
            error_msg = _truncate("".join(traceback.format_exception(exc)))
            retry_count = self.request.retries

            async def _record_failure() -> None:
                if log_id is not None:
                    await _mark_log_failed(log_id, exc)
                await _write_dead_letter(
                    task_name=task_name,
                    payload=payload,
                    celery_task_id=task_id,
                    error_msg=error_msg,
                    retry_count=retry_count,
                )

            loop = self._ensure_loop()
            loop.run_until_complete(_record_failure())
        except Exception:  # noqa: BLE001
            logger.exception("celery_on_failure_hook_failed")
        finally:
            super().on_failure(exc, task_id, args, kwargs, einfo)


async def _mark_log_failed(log_id: int, exc: BaseException) -> None:
    async with AsyncSessionLocal() as session:
        log = await session.get(CollectorLog, log_id)
        if log is None:
            return
        log.status = CollectorStatus.FAILED
        log.finished_at = datetime_now_utc()
        log.error_msg = _truncate(f"{type(exc).__name__}: {exc}")
        await session.commit()


async def _write_dead_letter(
    task_name: str,
    payload: dict[str, Any],
    celery_task_id: str,
    error_msg: str,
    retry_count: int,
) -> None:
    log_id = payload.get("log_id")
    async with AsyncSessionLocal() as session:
        session.add(
            CollectorDeadLetter(
                task_name=task_name,
                source=payload.get("preferred_source"),
                payload=payload,
                celery_task_id=celery_task_id,
                collector_log_id=log_id,
                error_msg=error_msg,
                retry_count=retry_count,
            )
        )
        await session.commit()


def datetime_now_utc() -> datetime:
    return datetime.now(timezone.utc)


@app.task(
    bind=True,
    base=LogAwareTask,
    name="collector.celery_tasks.run_collector_task",
)
def run_collector_task(self: LogAwareTask, payload: dict[str, Any]) -> dict[str, Any]:
    """Execute a collector task in a prefork worker.

    The payload must contain at least ``task``.  ``log_id`` is optional for
    ad-hoc / scheduled entries that do not originate from the dispatcher.

    All async work runs on the child process's persistent event loop so that
    SQLAlchemy's asyncpg connection pool is not shared across different loops.
    """
    configure_logging()
    payload = dict(payload)
    payload["celery_task_id"] = self.request.id

    async def _execute() -> dict[str, Any]:
        try:
            result = await run_task(payload)
            await _update_task_schedule_state(payload, result, error=None)
            return _result_to_dict(result)
        except SoftTimeLimitExceeded as exc:
            logger.warning(
                "collector_task_soft_timeout",
                task=payload.get("task"),
                celery_task_id=self.request.id,
                retries=self.request.retries,
            )
            log_id = payload.get("log_id")
            if log_id is not None:
                await _mark_log_timeout(log_id)
            await _update_task_schedule_state(
                payload,
                None,
                error=f"SoftTimeLimitExceeded after {self.request.retries} retries",
            )
            raise exc
        except Exception as exc:
            await _update_task_schedule_state(
                payload, None, error=f"{type(exc).__name__}: {exc}"
            )
            raise exc

    loop = self._ensure_loop()
    return loop.run_until_complete(_execute())


async def _dispose_async_engines() -> None:
    """Dispose asyncpg connection pools.

    Kept as a helper for explicit cleanup (e.g. worker shutdown).  With the
    persistent event loop used by :class:`AsyncTask`, per-task disposal is no
    longer required because connections stay bound to the same loop.
    """
    from app.core import database as app_database
    from collector.core.base import dispose_engine

    try:
        if app_database.engine is not None:
            await app_database.engine.dispose()
    except Exception:  # noqa: BLE001
        logger.exception("dispose_app_engine_failed")

    try:
        await dispose_engine()
    except Exception:  # noqa: BLE001
        logger.exception("dispose_collector_engine_failed")


async def _mark_log_timeout(log_id: int) -> None:
    async with AsyncSessionLocal() as session:
        log = await session.get(CollectorLog, log_id)
        if log is None:
            return
        log.status = CollectorStatus.FAILED
        log.finished_at = datetime_now_utc()
        log.error_msg = "Task exceeded soft time limit"
        await session.commit()


async def _update_task_schedule_state(
    payload: dict[str, Any],
    result: CollectResult | None,
    error: str | None,
) -> None:
    """Update collector_task lifecycle fields for scheduled runs."""
    task_name = payload.get("task_name") or payload.get("task")
    if not task_name:
        return

    async with AsyncSessionLocal() as session:
        task = await session.scalar(
            select(CollectorTask).where(CollectorTask.task_name == task_name)
        )
        if task is None:
            return
        task.last_run_at = datetime_now_utc()
        if result is not None:
            task.last_status = result.status.value
            task.last_error = "\n".join(result.errors) if result.errors else None
        else:
            task.last_status = CollectorStatus.FAILED
            task.last_error = error
        await session.commit()


def _result_to_dict(result: CollectResult) -> dict[str, Any]:
    return {
        "source": result.source,
        "data_type": result.data_type,
        "status": result.status.value,
        "items_collected": result.items_collected,
        "items_stored": result.items_stored,
        "errors": result.errors,
        "started_at": result.started_at.isoformat() if result.started_at else None,
        "finished_at": result.finished_at.isoformat() if result.finished_at else None,
        "metadata": result.metadata or {},
    }
