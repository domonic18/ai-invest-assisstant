"""采集任务的 Celery app 工厂与队列路由。

Celery app 刻意保持精简且数据驱动：不硬编码任何具体任务名。队列、超时与
重试策略均从 ``collector.runtime.registry`` 的 ``TaskSpec`` 声明派生。
"""

from typing import Any

import structlog
from celery import Celery
from celery.signals import worker_process_init, worker_process_shutdown
from kombu import Queue

from app.constants.collector import CollectorQueue
from collector.core import config as collector_config
from collector.core.logging import configure_logging
from collector.runtime.registry import TASK_SPECS

APP_NAME = "collector"

__all__ = [
    "app",
    "resolve_queue",
    "resolve_task_options",
]

DEFAULT_QUEUE = CollectorQueue.BATCH

QUEUE_NAMES = (
    CollectorQueue.REALTIME,
    CollectorQueue.BATCH,
    CollectorQueue.HEAVY,
)

# TaskSpec 未覆盖时的默认策略。
QUEUE_DEFAULTS: dict[str, dict[str, Any]] = {
    CollectorQueue.REALTIME: {
        "soft_time_limit": 60,
        "hard_time_limit": 120,
        "max_retries": 3,
        "retry_backoff": 30,
    },
    CollectorQueue.BATCH: {
        "soft_time_limit": 300,
        "hard_time_limit": 600,
        "max_retries": 3,
        "retry_backoff": 60,
    },
    CollectorQueue.HEAVY: {
        "soft_time_limit": 1800,
        "hard_time_limit": 3600,
        "max_retries": 2,
        "retry_backoff": 300,
    },
}


def make_celery_app() -> Celery:
    """创建并配置采集器 Celery 应用。"""
    app = Celery(APP_NAME)
    app.conf.update(
        broker_url=collector_config.celery_broker_url,
        result_backend=collector_config.celery_result_backend,
        task_serializer="json",
        accept_content=["json"],
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        result_expires=collector_config.celery_result_expires,
        task_default_queue=collector_config.celery_task_default_queue or DEFAULT_QUEUE,
        task_queues=tuple(
            Queue(name, exchange=name, routing_key=name) for name in QUEUE_NAMES
        ),
    )
    # 自动发现 collector 包内的任务。
    app.autodiscover_tasks(["collector"], force=True)
    return app


app = make_celery_app()
# 显式导入任务模块，使 ``run_collector_task`` 得以注册——
# 本文件名为 ``celery_tasks.py`` 而非 ``tasks.py``。
import collector.celery_tasks  # noqa: F401, E402


def resolve_queue(task_name: str, preferred_source: str | None = None) -> str:
    """解析采集任务的目标 Celery 队列。

    解析顺序：
    1. dispatcher 在 ``apply_async`` 传入显式 ``queue`` 时应用
       ``CollectorTask.queue`` 覆盖。
    2. ``TaskSpec.queue`` 默认值。
    3. 兜底 ``collector.batch``。
    """
    spec = TASK_SPECS.get(task_name)
    queue: str | None = spec.queue if spec is not None else None

    if queue is not None and not queue.startswith("collector."):
        queue = f"collector.{queue}"

    return queue or DEFAULT_QUEUE


def resolve_task_options(
    task_name: str,
    preferred_source: str | None = None,
    queue_override: str | None = None,
) -> dict[str, Any]:
    """返回任务的 Celery ``apply_async`` 选项。

    选项包括 ``queue``、``soft_time_limit``、``max_retries`` 与
    ``retry_backoff``。TaskSpec 覆盖值优先于队列默认值；显式 ``queue_override``
    （如来自 ``CollectorTask.queue``）优先于一切。
    """
    queue = queue_override or resolve_queue(task_name, preferred_source)
    if queue is not None and not queue.startswith("collector."):
        queue = f"collector.{queue}"
    defaults = QUEUE_DEFAULTS.get(queue, QUEUE_DEFAULTS[DEFAULT_QUEUE])
    spec = TASK_SPECS.get(task_name)

    soft_time_limit = (
        spec.soft_time_limit if spec is not None and spec.soft_time_limit is not None
        else defaults["soft_time_limit"]
    )
    max_retries = (
        spec.max_retries if spec is not None and spec.max_retries is not None
        else defaults["max_retries"]
    )

    return {
        "queue": queue,
        "soft_time_limit": soft_time_limit,
        "max_retries": max_retries,
        "retry_backoff": defaults["retry_backoff"],
        "retry_backoff_max": defaults["hard_time_limit"],
    }


@app.on_after_configure.connect
def _setup_logging(sender: Celery, **kwargs: Any) -> None:  # noqa: ARG001
    """确保 Celery 主进程完成结构化日志配置。"""
    configure_logging()


@worker_process_init.connect
def _init_worker_process(**kwargs: Any) -> None:  # noqa: ARG001
    """在每个 prefork 子进程中重建 SQLAlchemy engine。

    父进程在模块导入时创建了异步 engine；子进程不得复用这些连接。这里释放
    继承的 engine 并创建新的，然后重新绑定 ``AsyncSessionLocal``，使所有已
    导入的引用都指向新 engine。
    """
    import asyncio

    import sqlalchemy.ext.asyncio as async_sa

    from app.core import database as app_database
    from collector.core.base import dispose_engine
    from collector.core.logging import configure_logging as configure_child_logging

    configure_child_logging()
    logger = structlog.get_logger(__name__)
    logger.info("worker_process_init_recreate_engines")

    # 释放从父进程继承的 engine。
    try:
        app_database.engine.sync_engine.dispose(close=False)
    except Exception:  # noqa: BLE001
        pass

    try:
        asyncio.run(app_database.engine.dispose())
    except Exception:  # noqa: BLE001
        pass

    try:
        asyncio.run(dispose_engine())
    except Exception:  # noqa: BLE001
        pass

    # 在子进程中创建全新的异步 engine 并重新绑定 session maker。
    new_engine = async_sa.create_async_engine(
        app_database.engine.url.render_as_string(hide_password=False),
        echo=app_database.engine.echo,
        future=True,
        pool_pre_ping=True,
    )
    app_database.engine = new_engine
    app_database.AsyncSessionLocal.configure(bind=new_engine)
    logger.info("worker_process_recreated_app_engine")


@worker_process_shutdown.connect
def _shutdown_worker_process(**kwargs: Any) -> None:  # noqa: ARG001
    """prefork 子进程退出时释放 SQLAlchemy engine。"""
    import asyncio

    from app.core import database as app_database
    from collector.core.base import dispose_engine
    from collector.core.logging import configure_logging as configure_child_logging

    configure_child_logging()
    logger = structlog.get_logger(__name__)
    logger.info("worker_process_shutdown_dispose_engines")

    try:
        asyncio.run(app_database.engine.dispose())
    except Exception:  # noqa: BLE001
        pass

    try:
        asyncio.run(dispose_engine())
    except Exception:  # noqa: BLE001
        pass
