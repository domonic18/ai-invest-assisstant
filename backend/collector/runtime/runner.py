"""统一任务执行器：worker/scheduler/CLI/SCF 共享的执行路径。

职责：
- 生成 task_run_id 并绑定 structlog contextvars，贯穿任务的全部日志；
- 按 TASK_MAP 分发执行，保留多渠道 fallback 错误链；
- collector_log 唯一写入口：dispatcher 创建的 pending 行由本模块推进
  running → 终态；无 log_id 的入口（scheduler/CLI/SCF）由本模块直接
  插入完整记录；
- 异常时把 traceback（截断 4000 字符）写入 error_msg。
"""

import traceback
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any, cast

import structlog

from app.core.database import AsyncSessionLocal
from app.models.collector_log import CollectorLog
from collector.core.base import CollectResult
from collector.core.logging import bind_task_context, clear_task_context
from collector.runtime.registry import TASK_MAP, TASK_SPECS

logger = structlog.get_logger(__name__)

_ERROR_MSG_MAX_LEN = 4000


def _build_task_kwargs(task_name: str, params: dict[str, Any]) -> dict[str, Any]:
    """根据请求参数为采集任务函数构建 kwargs。

    任务级参数白名单由 TASK_SPECS 声明表派生，registry 之外不再重复维护。
    """
    kwargs: dict[str, Any] = {}

    preferred_source = params.get("preferred_source")
    if preferred_source is not None:
        kwargs["preferred_source"] = preferred_source

    symbols = params.get("symbols")
    if symbols is not None:
        kwargs["symbols"] = symbols

    spec = TASK_SPECS.get(task_name)
    if spec is not None:
        for param_name in spec.param_keys:
            value = params.get(param_name)
            if value is not None:
                kwargs[param_name] = value

    return kwargs


async def run_task(params: dict[str, Any]) -> CollectResult:
    """执行 ``params`` 描述的采集任务并持久化其日志。

    Args:
        params: 必须包含 ``task``（任务名）。可选字段取决于具体任务，如
            ``symbols``、``period``、``start_date``、``end_date``、
            ``report_types``、``sector_type``、``indicators``、``report_date``、
            ``preferred_source``。``log_id`` 指向 dispatcher 创建的 pending
            CollectorLog 行。

    Returns:
        采集结果。
    """
    task_name: str = params.get("task", "")
    log_id = params.get("log_id")
    celery_task_id = params.get("celery_task_id")
    task_run_id = uuid.uuid4().hex[:8]
    bind_task_context(
        task_run_id=task_run_id,
        task=task_name or "unknown",
        source=params.get("preferred_source"),
        celery_task_id=celery_task_id,
    )

    try:
        if not task_name:
            raise ValueError("Missing required field: task")
        coro = cast(
            Callable[..., Awaitable[CollectResult]] | None,
            TASK_MAP.get(task_name),
        )
        if coro is None:
            raise ValueError(
                f"Unknown task: {task_name}. Available: {list(TASK_MAP.keys())}"
            )

        if log_id is not None:
            await _mark_running(log_id)

        kwargs = _build_task_kwargs(task_name, params)
        logger.info("collector_task_started", log_id=log_id, kwargs=kwargs)
        result = await coro(**kwargs)

        await _persist_result(task_name, log_id, celery_task_id, task_run_id, result)
        logger.info(
            "collector_task_finished",
            status=result.status.value,
            collected=result.items_collected,
            stored=result.items_stored,
            errors=len(result.errors),
        )
        return result
    except Exception as exc:
        if log_id is not None:
            await _persist_error(log_id, celery_task_id, exc)
        logger.exception("collector_task_failed")
        raise
    finally:
        clear_task_context()


def _truncate(text: str) -> str:
    return text[:_ERROR_MSG_MAX_LEN]


async def _mark_running(log_id: int) -> None:
    async with AsyncSessionLocal() as session:
        log = await session.get(CollectorLog, log_id)
        if log is not None:
            log.status = "running"
            log.started_at = datetime.now(timezone.utc)
            await session.commit()


async def _persist_result(
    task_name: str,
    log_id: int | None,
    celery_task_id: str | None,
    task_run_id: str,
    result: CollectResult,
) -> None:
    """写入终态：有 log_id 更新 pending 行，否则插入完整记录。"""
    error_msg = "\n".join(result.errors) if result.errors else None
    async with AsyncSessionLocal() as session:
        if log_id is not None:
            log = await session.get(CollectorLog, log_id)
            if log is None:
                return
            log.status = result.status.value
            log.source = result.source
            log.finished_at = result.finished_at or datetime.now(timezone.utc)
            log.records_count = result.items_stored
            log.error_msg = _truncate(error_msg) if error_msg else None
            if celery_task_id is not None:
                log.celery_task_id = celery_task_id
            log.meta = {
                **(log.meta or {}),
                **(result.metadata or {}),
                "task_run_id": task_run_id,
                "celery_task_id": celery_task_id,
            }
        else:
            session.add(
                CollectorLog(
                    task_name=task_name,
                    source=result.source,
                    status=result.status.value,
                    started_at=result.started_at,
                    finished_at=result.finished_at or datetime.now(timezone.utc),
                    records_count=result.items_stored,
                    error_msg=_truncate(error_msg) if error_msg else None,
                    celery_task_id=celery_task_id,
                    meta={**(result.metadata or {}), "task_run_id": task_run_id, "celery_task_id": celery_task_id},
                )
            )
        await session.commit()


async def _persist_error(log_id: int, celery_task_id: str | None, exc: Exception) -> None:
    error_msg = _truncate(traceback.format_exc())
    async with AsyncSessionLocal() as session:
        log = await session.get(CollectorLog, log_id)
        if log is not None:
            log.status = "failed"
            log.finished_at = datetime.now(timezone.utc)
            log.error_msg = error_msg
            if celery_task_id is not None:
                log.celery_task_id = celery_task_id
            await session.commit()


def run_task_sync(params: dict[str, Any]) -> CollectResult:
    """在全新事件循环中运行异步任务的同步包装。"""
    import asyncio

    return asyncio.run(run_task(params))
