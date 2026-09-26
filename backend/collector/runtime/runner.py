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
from sqlalchemy import or_, select

from app.core.clock import today_cn
from app.core.database import AsyncSessionLocal
from app.models.collector_log import CollectorLog
from app.models.collector_task import CollectorTask
from app.services.market.trade_calendar_service import (
    SCHEDULE_NON_TRADING,
    SCHEDULE_TRADING,
    classify_schedule_day,
)
from collector.core.base import CollectResult, CollectStatus
from collector.core.logging import bind_task_context, clear_task_context
from collector.runtime.registry import TASK_MAP, TASK_SPECS
from collector.runtime.specs.base import TaskSpec

logger = structlog.get_logger(__name__)

_ERROR_MSG_MAX_LEN = 4000

# 显式日期参数 = 手动补跑意图，豁免交易日预检（保留周末/节假日手动补跑能力）
_EXPLICIT_DATE_PARAM_KEYS = frozenset({"trade_date", "start_date", "end_date"})


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
        else:
            # beat/定时路径无 dispatcher 预建行：执行前落 running 行，挂死任务
            # 在日志页立即可见（2026-09-23 事故排查曾因此多花 30+ 分钟）。
            # 软超时重试的每次尝试各产生一条行；被硬限 SIGKILL 的行停留在
            # running，正是诊断证据。
            log_id = await _create_running_row(task_name, celery_task_id)

        kwargs = _build_task_kwargs(task_name, params)
        spec = TASK_SPECS.get(task_name)
        skipped = await _precheck_trade_day(params, kwargs, spec, task_name)
        if skipped is not None:
            await _persist_result(
                task_name, log_id, celery_task_id, task_run_id, skipped
            )
            logger.info(
                "collector_task_finished",
                status=skipped.status.value,
                collected=0,
                stored=0,
                errors=0,
            )
            return skipped
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


async def _precheck_trade_day(
    params: dict[str, Any],
    kwargs: dict[str, Any],
    spec: TaskSpec | None,
    task_name: str,
) -> CollectResult | None:
    """trade_day_only 任务的交易日预检：非交易日/日历未覆盖 → SKIPPED（不出网络）。

    - 预检开关按 collector_task 实例行读取（后台可改，无需重启）；
      beat 传实例名（task_name），手动路径传任务类型名（task），两者都按行匹配；
    - 显式日期参数（trade_date/start_date/end_date）= 手动补跑，豁免；
    - 日历未覆盖当日（unknown）同样拒绝并注明（D5：不静默回退周末启发）。
    """
    if _EXPLICIT_DATE_PARAM_KEYS.intersection(kwargs):
        return None
    lookup_name = params.get("task_name") or task_name
    async with AsyncSessionLocal() as session:
        trade_day_only = (
            await session.execute(
                select(CollectorTask.trade_day_only)
                .where(
                    or_(
                        CollectorTask.task_name == lookup_name,
                        CollectorTask.task_type == lookup_name,
                    )
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if not trade_day_only:
            return None
        verdict = await classify_schedule_day(session, today_cn())
    if verdict == SCHEDULE_TRADING:
        return None
    message = (
        "非交易日，按 trade_day_only 预检跳过"
        if verdict == SCHEDULE_NON_TRADING
        else "交易日历未覆盖当日，拒绝调度（请在后台重新生成交易日历）"
    )
    logger.warning(
        "collector_task_precheck_skipped", task=task_name, verdict=verdict
    )
    return CollectResult(
        source=params.get("preferred_source") or "internal",
        data_type=spec.data_type if spec is not None else "unknown",
        status=CollectStatus.SKIPPED,
        message=message,
        metadata={"precheck": "trade_day_only"},
    )


async def _create_running_row(task_name: str, celery_task_id: str | None) -> int:
    """执行前插入 running 行，返回 id 供终态更新复用。"""
    async with AsyncSessionLocal() as session:
        log = CollectorLog(
            task_name=task_name,
            status="running",
            started_at=datetime.now(timezone.utc),
            celery_task_id=celery_task_id,
        )
        session.add(log)
        await session.commit()
        return log.id


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
            log.message = result.message
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
                    message=result.message,
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
