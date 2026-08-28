"""Celery app factory and queue routing for collector tasks.

The Celery app is intentionally thin and data-driven: it does not hard-code
individual task names.  Queue, timeout, and retry policies are derived from
``TaskSpec`` declarations in ``collector.runtime.registry``.
"""

from typing import Any

import structlog
from celery import Celery
from celery.signals import worker_process_init
from kombu import Queue

from collector.core import config as collector_config
from collector.core.logging import configure_logging
from collector.runtime.registry import TASK_SPECS

APP_NAME = "collector"

__all__ = [
    "app",
    "resolve_queue",
    "resolve_task_options",
]

DEFAULT_QUEUE = "collector.batch"

QUEUE_NAMES = (
    "collector.realtime",
    "collector.batch",
    "collector.heavy",
)

# Default policies when a TaskSpec does not override them.
QUEUE_DEFAULTS: dict[str, dict[str, Any]] = {
    "collector.realtime": {
        "soft_time_limit": 60,
        "hard_time_limit": 120,
        "max_retries": 3,
        "retry_backoff": 30,
    },
    "collector.batch": {
        "soft_time_limit": 300,
        "hard_time_limit": 600,
        "max_retries": 3,
        "retry_backoff": 60,
    },
    "collector.heavy": {
        "soft_time_limit": 1800,
        "hard_time_limit": 3600,
        "max_retries": 2,
        "retry_backoff": 300,
    },
}


def make_celery_app() -> Celery:
    """Create and configure the collector Celery application."""
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
    # Auto-discover tasks in the collector package.
    app.autodiscover_tasks(["collector"], force=True)
    return app


app = make_celery_app()
# Explicitly import the task module so ``run_collector_task`` is registered
# even though the file is named ``celery_tasks.py`` instead of ``tasks.py``.
import collector.celery_tasks  # noqa: F401, E402


def resolve_queue(task_name: str, preferred_source: str | None = None) -> str:
    """Resolve the target Celery queue for a collector task.

    Resolution order:
    1. ``CollectorTask.queue`` override is applied by the dispatcher when it
       passes an explicit ``queue`` in ``apply_async``.
    2. ``TaskSpec.queue`` default.
    3. Fallback to ``collector.batch``.
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
    """Return Celery ``apply_async`` options for a task.

    Options include ``queue``, ``soft_time_limit``, ``max_retries``, and
    ``retry_backoff``.  TaskSpec overrides take precedence over queue defaults.
    An explicit ``queue_override`` (e.g. from ``CollectorTask.queue``) wins over
    everything else.
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
    """Ensure structured logging is configured in the Celery master process."""
    configure_logging()


@worker_process_init.connect
def _init_worker_process(**kwargs: Any) -> None:  # noqa: ARG001
    """Recreate SQLAlchemy engines in each prefork child process.

    The parent process creates async engines during module import; child
    processes must not reuse those connections.  We dispose the inherited
    engines and create fresh ones, then rebind ``AsyncSessionLocal`` so that
    all imported references see the new engine.
    """
    import asyncio

    import sqlalchemy.ext.asyncio as async_sa

    from app.core import database as app_database
    from collector.core.base import dispose_engine
    from collector.core.logging import configure_logging as configure_child_logging

    configure_child_logging()
    logger = structlog.get_logger(__name__)
    logger.info("worker_process_init_recreate_engines")

    # Dispose inherited engines from the parent process.
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

    # Create a brand-new async engine in the child and rebind the session maker.
    new_engine = async_sa.create_async_engine(
        app_database.engine.url.render_as_string(hide_password=False),
        echo=app_database.engine.echo,
        future=True,
    )
    app_database.engine = new_engine
    app_database.AsyncSessionLocal.configure(bind=new_engine)
    logger.info("worker_process_recreated_app_engine")
