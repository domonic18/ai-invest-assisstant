"""采集任务的腾讯云 SCF Job handler。

SCF 中的用法：
    执行方法: index.main_handler
    触发方式: 定时触发 / 事件触发
    触发事件: {"task": "financial-report", "symbols": ["000001"], "report_types": ["年报"]}

只负责 SCF 事件解析与响应包装；任务执行统一走
``collector.runtime.runner.run_task``，与本地 worker/scheduler/CLI 共享路径。
"""

import json
import logging
from typing import Any

from collector.runtime.runner import run_task_sync

logger = logging.getLogger(__name__)


def _parse_event(event: dict[str, Any] | str | None) -> dict[str, Any]:
    """把 SCF 事件解析为任务参数字典。"""
    if event is None:
        return {}
    if isinstance(event, str):
        try:
            parsed: dict[str, Any] = json.loads(event)
            return parsed
        except json.JSONDecodeError:
            return {"task": event}
    return event


def main_handler(
    event: dict[str, Any] | str | None, context: Any
) -> dict[str, Any]:
    """SCF 入口函数。

    Args:
        event: 包含任务参数的 SCF 触发事件。
        context: SCF 运行时上下文。

    Returns:
        采集结果摘要。
    """
    from collector.core.logging import configure_logging

    configure_logging()

    params = _parse_event(event)
    logger.info("SCF collector started with params: %s", params)

    try:
        result = run_task_sync(params)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Collector task failed")
        return {
            "statusCode": 500,
            "body": json.dumps({"status": "failed", "error": str(exc)}),
        }

    response = {
        "statusCode": 200 if result.status.value == "success" else 500,
        "body": json.dumps(
            {
                "source": result.source,
                "data_type": result.data_type,
                "status": result.status.value,
                "items_collected": result.items_collected,
                "items_stored": result.items_stored,
                "errors": result.errors,
            },
            ensure_ascii=False,
        ),
    }
    logger.info("SCF collector finished: %s", response["body"])
    return response
