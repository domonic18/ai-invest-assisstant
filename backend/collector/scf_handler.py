"""Tencent SCF Job handler for collector tasks.

Usage in SCF:
    执行方法: index.main_handler
    触发方式: 定时触发
    触发事件: {"task": "kline", "period": "daily"}
"""

import asyncio
import json
import logging
from typing import Any

from collector.base import CollectResult
from collector.tasks import TASK_MAP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _parse_event(event: dict[str, Any] | str | None) -> dict[str, Any]:
    """解析 SCF 事件为任务参数字典。"""
    if event is None:
        return {}
    if isinstance(event, str):
        try:
            parsed: dict[str, Any] = json.loads(event)
            return parsed
        except json.JSONDecodeError:
            return {"task": event}
    return event


async def _run_task(params: dict[str, Any]) -> CollectResult:
    """根据参数运行对应采集任务。"""
    from collector.tasks import collect_auction, collect_fund_flow, collect_kline, collect_news

    task_name = params.get("task", "kline")
    if task_name == "kline":
        return await collect_kline(period=params.get("period", "daily"))
    if task_name == "auction":
        return await collect_auction()
    if task_name == "fund-flow":
        return await collect_fund_flow()
    if task_name == "news":
        return await collect_news()

    raise ValueError(f"Unknown task: {task_name}. Available: {list(TASK_MAP.keys())}")


def main_handler(event: dict[str, Any] | str | None, context: Any) -> dict[str, Any]:
    """SCF 入口函数。

    Args:
        event: SCF 触发事件，可包含 task/period/symbols 等参数。
        context: SCF 运行时上下文。

    Returns:
        采集结果摘要。
    """
    params = _parse_event(event)
    logger.info("SCF collector started with params: %s", params)

    try:
        result = _run_task_sync(params)
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


def _run_task_sync(params: dict[str, Any]) -> CollectResult:
    """同步包装：在新的事件循环中执行异步采集任务。"""
    return asyncio.run(_run_task(params))
