"""Tencent SCF Job handler and unified local runner for collector tasks.

Usage in SCF:
    执行方法: index.main_handler
    触发方式: 定时触发 / 事件触发
    触发事件: {"task": "financial-report", "symbols": ["000001"], "report_types": ["年报"]}

This module is also imported by the local collector worker so that Docker and SCF
share a single execution path.
"""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any, cast

from collector.base import CollectResult
from collector.tasks import TASK_MAP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Mapping from JSON parameter names to collector task function argument names.
# Every task receives ``preferred_source``; other params are task-specific.
_TASK_PARAM_BUILDERS: dict[
    str, dict[str, list[str]]
] = {
    "kline": {"period": ["period"]},
    "auction": {},
    "fund-flow": {},
    "news": {},
    "company-profile": {},
    "disclosure": {"start_date": ["start_date"], "end_date": ["end_date"]},
    "sector-fund-flow": {"sector_type": ["sector_type"]},
    "dragon-list": {"start_date": ["start_date"], "end_date": ["end_date"]},
    "research-report": {},
    "financial-report": {
        "start_date": ["start_date"],
        "end_date": ["end_date"],
        "report_types": ["report_types"],
    },
    "ipo-info": {},
    "fund-holdings": {"report_date": ["report_date"]},
    "macro": {"indicators": ["indicators"]},
    "stock-list": {},
    "limit-up-pool": {"trade_date": ["trade_date"]},
}


def _parse_event(event: dict[str, Any] | str | None) -> dict[str, Any]:
    """Parse an SCF event into a task parameter dictionary."""
    if event is None:
        return {}
    if isinstance(event, str):
        try:
            parsed: dict[str, Any] = json.loads(event)
            return parsed
        except json.JSONDecodeError:
            return {"task": event}
    return event


def _build_task_kwargs(task_name: str, params: dict[str, Any]) -> dict[str, Any]:
    """Build kwargs for the collector task function from request params."""
    kwargs: dict[str, Any] = {}

    preferred_source = params.get("preferred_source")
    if preferred_source is not None:
        kwargs["preferred_source"] = preferred_source

    symbols = params.get("symbols")
    if symbols is not None:
        kwargs["symbols"] = symbols

    param_builders = _TASK_PARAM_BUILDERS.get(task_name, {})
    for param_name, arg_names in param_builders.items():
        value = params.get(param_name)
        if value is not None:
            for arg_name in arg_names:
                kwargs[arg_name] = value

    return kwargs


async def _run_task(params: dict[str, Any]) -> CollectResult:
    """Run the collector task described by ``params``.

    Args:
        params: Must contain ``task`` (task name). Optional fields depend on the
            task, e.g. ``symbols``, ``period``, ``start_date``, ``end_date``,
            ``report_types``, ``sector_type``, ``indicators``, ``report_date``,
            ``preferred_source``.

    Returns:
        The collector result.
    """
    task_name: str = params.get("task", "")
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

    kwargs = _build_task_kwargs(task_name, params)
    logger.info("Running collector task: %s with kwargs: %s", task_name, kwargs)
    result: CollectResult = await coro(**kwargs)
    return result


def _run_task_sync(params: dict[str, Any]) -> CollectResult:
    """Synchronous wrapper that runs the async task in a fresh event loop."""
    return asyncio.run(_run_task(params))


def main_handler(
    event: dict[str, Any] | str | None, context: Any
) -> dict[str, Any]:
    """SCF entry point.

    Args:
        event: SCF trigger event containing task parameters.
        context: SCF runtime context.

    Returns:
        Collection result summary.
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
