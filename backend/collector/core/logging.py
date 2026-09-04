"""Collector 日志配置 — structlog 统一入口。

所有 collector 模块的日志（无论 structlog 还是 stdlib logging）都经
ProcessorFormatter 输出为统一格式；通过 structlog contextvars 绑定
task_run_id/task/source 等上下文，贯穿一次任务执行的所有日志。

环境变量：
- LOG_LEVEL: 日志级别，默认 INFO
- LOG_FORMAT: json（默认）/ console（本地开发可读格式）
"""

import logging
import os
import sys

import structlog

_shared_processors: list = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
]


def configure_logging(level: str | None = None) -> None:
    """配置 structlog + stdlib 桥接，幂等可重复调用。"""
    log_level = (level or os.getenv("LOG_LEVEL") or "INFO").upper()
    json_logs = os.getenv("LOG_FORMAT", "json").lower() != "console"

    structlog.configure(
        processors=[
            *_shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    renderer = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer()
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=_shared_processors,
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(log_level)


def bind_task_context(
    task_run_id: str,
    task: str,
    source: str | None = None,
    celery_task_id: str | None = None,
) -> None:
    """绑定一次任务执行的上下文，后续日志自动携带这些字段。"""
    context: dict[str, str] = {"task_run_id": task_run_id, "task": task}
    if source:
        context["source"] = source
    if celery_task_id:
        context["celery_task_id"] = celery_task_id
    structlog.contextvars.bind_contextvars(**context)


def clear_task_context() -> None:
    """任务结束后清理上下文，避免泄漏到下一次执行。"""
    structlog.contextvars.unbind_contextvars(
        "task_run_id", "task", "source", "celery_task_id"
    )
