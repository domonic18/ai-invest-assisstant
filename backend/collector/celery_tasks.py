"""采集执行的 Celery 任务包装。

本模块暴露通用采集任务与代理连通性探测任务。采集任务可执行
``collector.runtime.registry.TASK_MAP`` 中注册的任意采集 spider，任务体复用
``collector.runtime.runner.run_task``，日志、状态持久化与多渠道 fallback
行为保持不变。
"""

import asyncio
import time
import traceback
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, cast

import structlog
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded
from curl_cffi.requests import Session as CffiSession
from sqlalchemy import select

from app.constants.collector import CollectorStatus
from app.core.database import AsyncSessionLocal
from app.models.collector_dead_letter import CollectorDeadLetter
from app.models.collector_log import CollectorLog
from app.models.collector_task import CollectorTask
from collector.celery_app import app, resolve_task_options
from collector.core.base import CollectResult
from collector.core.logging import configure_logging
from collector.runtime.runner import run_task

if TYPE_CHECKING:
    from curl_cffi.requests import ProxySpec

logger = structlog.get_logger(__name__)

_ERROR_MSG_MAX_LEN = 4000

# 代理连通性探测：Google 无鉴权 204 端点，探测的是代理链路而非目标站 TLS
# 指纹。单次尝试不重试——探测要求快速给出结论，重试只会把失败延迟三倍。
_PROXY_TEST_URL = "https://www.google.com/generate_204"
_PROXY_TEST_PROBE_SECONDS = 8.0


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
            options = resolve_task_options(payload.get("task", ""))
            retries = self.request.retries
            if retries < options["max_retries"]:
                # 软超时可能是采集源瞬时不稳：按队列退避策略重试；重试期间
                # 不写终态日志（collector_log 由下次尝试复用并覆盖）。
                logger.warning(
                    "collector_task_soft_timeout_retry",
                    task=payload.get("task"),
                    celery_task_id=self.request.id,
                    retries=retries,
                    countdown=options["retry_backoff"],
                )
                await _update_task_schedule_state(
                    payload,
                    None,
                    error=f"SoftTimeLimitExceeded after {retries} retries",
                )
                raise self.retry(
                    countdown=options["retry_backoff"],
                    max_retries=options["max_retries"],
                    exc=exc,
                ) from exc
            logger.error(
                "collector_task_soft_timeout_exhausted",
                task=payload.get("task"),
                celery_task_id=self.request.id,
                retries=retries,
            )
            log_id = payload.get("log_id")
            if log_id is not None:
                await _mark_log_timeout(log_id)
            await _update_task_schedule_state(
                payload,
                None,
                error=f"SoftTimeLimitExceeded after {retries} retries",
            )
            raise exc
        except Exception as exc:
            # 延迟导入：避免 celery_tasks 顶层依赖 app.services 聚合包的导入序。
            from app.services.market.anomaly_common import AnomalyInputNotReadyError
            from app.services.review import ReviewInputDataNotReadyError

            if isinstance(exc, (ReviewInputDataNotReadyError, AnomalyInputNotReadyError)):
                # 收盘批数据（板块资金/指数K线/板块与全市场快照）尚未落库：
                # 10 分钟后重试，最多 3 次；重试耗尽后 exc 原样抛出，走 on_failure 死信。
                logger.warning(
                    "collector_task_input_not_ready",
                    task=payload.get("task"),
                    celery_task_id=self.request.id,
                    retries=self.request.retries,
                )
                await _update_task_schedule_state(
                    payload, None, error=f"{type(exc).__name__}: {exc}"
                )
                raise self.retry(countdown=600, max_retries=3, exc=exc) from exc
            await _update_task_schedule_state(
                payload, None, error=f"{type(exc).__name__}: {exc}"
            )
            raise exc

    loop = self._ensure_loop()
    return loop.run_until_complete(_execute())


@app.task(name="collector.celery_tasks.run_proxy_test")
def run_proxy_test(proxy_url: str) -> dict[str, Any]:
    """在 worker 所在机器经代理探测外网连通性。

    代理的使用方是采集 worker（如 49 生产服务器），管理后台所在的 SCF 出口
    IP 通常不在代理白名单内，直接从 API 侧探测会被安全组拦截——测试必须在
    实际消费代理的机器上执行。返回与
    ``app.schemas.proxy_config.ProxyConfigTestResponse`` 同形的 dict，探测
    失败不抛异常（避免走采集任务的死信钩子），失败信息放 ``error`` 字段。
    """
    proxies = {"http": proxy_url, "https": proxy_url}
    started = time.monotonic()
    try:
        # 每次探测新建会话：不污染共享 cffi 单例的 cookie 状态
        with CffiSession(impersonate="chrome") as session:
            response = session.get(
                _PROXY_TEST_URL,
                timeout=_PROXY_TEST_PROBE_SECONDS,
                # curl_cffi 静态类型将 proxies 声明为键受限 TypedDict，运行时即 dict
                proxies=cast("ProxySpec", proxies),
            )
        latency_ms = int((time.monotonic() - started) * 1000)
        ok = response.status_code == 204
        return {
            "ok": ok,
            "status_code": response.status_code,
            "latency_ms": latency_ms,
            "error": None if ok else f"HTTP {response.status_code}",
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "proxy_test_probe_failed", proxy_host=proxy_url, error=str(exc)
        )
        return {
            "ok": False,
            "status_code": None,
            "latency_ms": int((time.monotonic() - started) * 1000),
            "error": f"{type(exc).__name__}: {exc}",
        }


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
