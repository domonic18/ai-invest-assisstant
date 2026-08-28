"""采集执行的 Celery 任务包装。

本模块只暴露一个通用 Celery 任务，可执行 ``collector.runtime.registry.TASK_MAP``
中注册的任意采集 spider。任务体复用 ``collector.runtime.runner.run_task``，
日志、状态持久化与多渠道 fallback 行为保持不变。
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
    """在子进程持久事件循环上运行异步代码的 Celery 任务基类。

    Celery prefork 子进程会复用同一进程执行多个任务。默认的 ``asyncio.run()``
    模式为每个任务创建再销毁一个事件循环，导致上一个循环的 asyncpg 连接残留在
    SQLAlchemy 连接池中；下一个任务在新循环上复用这些连接时会报
    ``asyncpg.exceptions.InterfaceError: another operation is in progress``。

    每个子进程保持一个循环可消除这种跨循环连接复用，让连接池正常预热。
    """

    _loop: asyncio.AbstractEventLoop | None = None

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        """返回子进程事件循环，必要时创建。"""
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop


class LogAwareTask(AsyncTask):
    """在硬性终止前写入超时状态的 Celery 任务基类。"""

    def on_failure(
        self,
        exc: BaseException,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        einfo: Any,
    ) -> None:
        """重试耗尽或失败为永久性时被调用。"""
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
    """在 prefork worker 中执行采集任务。

    payload 至少须包含 ``task``。``log_id`` 可选，供不来自 dispatcher 的临时
    或定时任务使用。

    所有异步工作都运行在子进程的持久事件循环上，避免 SQLAlchemy 的 asyncpg
    连接池被跨循环共享。
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
    """释放 asyncpg 连接池。

    保留为显式清理的辅助函数（如 worker 关闭时）。采用 :class:`AsyncTask` 的
    持久事件循环后，逐任务释放已无必要，因为连接始终绑定在同一循环上。
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
    """为定时任务运行更新 collector_task 的生命周期字段。"""
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
