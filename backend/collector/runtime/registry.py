"""任务注册表：TaskSpec 声明聚合 + 通用任务入口（含多渠道 fallback）。

TaskSpec 声明按数据类型族拆分在 ``collector/runtime/specs/`` 下维护，
本模块聚合为 TASK_SPECS 并应用队列覆盖；对外导入路径保持不变：
``from collector.runtime.registry import TASK_MAP, TASK_SPECS, TaskSpec``。
"""

import importlib
from collections.abc import Awaitable, Callable
from dataclasses import replace
from typing import Any, Literal

import structlog

from collector.core.base import BaseCollector, CollectResult, CollectStatus
from collector.runtime.resolver import resolve_channels_for_task
from collector.runtime.specs import ALL_SPECS
from collector.runtime.specs.base import TaskSpec

__all__ = ["TASK_MAP", "TASK_SPECS", "TaskSpec"]

logger = structlog.get_logger(__name__)

TASK_SPECS: dict[str, TaskSpec] = {spec.name: spec for spec in ALL_SPECS}

# 默认队列分配。保持此映射数据驱动，新增任务无需改框架代码；
# 也可通过 TaskSpec.queue 覆盖。
_QUEUE_OVERRIDES: dict[str, Literal["realtime", "batch", "heavy"]] = {
    # 概念成分股需对 500+ 概念逐个分页拉取（限流+网络延迟下实测约 22 分钟），
    # 超出 batch 队列 600s 硬超时，归入 heavy。
    "concept-constituents": "heavy",
    "auction": "realtime",
    "global-index": "realtime",
    "index-spot": "realtime",
    "index-minute": "realtime",
    "stock-minute": "realtime",
    "market-breadth": "realtime",
    "news": "realtime",
    "quote": "realtime",
    "company-profile": "heavy",
    "disclosure": "heavy",
    "financial-report": "heavy",
    "ipo-info": "heavy",
    "market-daily-review": "heavy",
    "limit-up-ai-review": "heavy",
    "stock-daily-analysis": "heavy",
    "research-report": "heavy",
    # 全链 AI 分析逐链分钟级，逐链串行走 heavy 专用 worker
    "chain-refresh": "heavy",
    # 自愈需串行重跑多个日 K 采集任务（全历史 upsert），耗时分钟级
    "kline-freshness": "heavy",
}

TASK_SPECS = {
    name: replace(spec, queue=_QUEUE_OVERRIDES.get(name, spec.queue))
    for name, spec in TASK_SPECS.items()
}


def _skipped_result(source: str, data_type: str) -> CollectResult:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    return CollectResult(
        source=source,
        data_type=data_type,
        status=CollectStatus.SKIPPED,
        items_collected=0,
        items_stored=0,
        errors=["没有启用任何可用的采集渠道"],
        started_at=now,
        finished_at=now,
    )


async def _resolve_task_channels(
    task_name: str,
    preferred_source: str | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    """解析 ``task_name`` 的有序渠道候选列表。

    返回 ``[(source, channel_config), ...]``，按管理端配置的优先级排序
    （指定 ``preferred_source`` 时置首）。返回空列表表示没有已启用的渠道
    支持该任务。
    """
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        channels = await resolve_channels_for_task(
            session, task_name, preferred_source
        )
        resolved: list[tuple[str, dict[str, Any]]] = []
        for channel in channels:
            config: dict[str, Any] = {
                "base_url": channel.base_url,
                "api_key": channel.api_key,
                "proxy_url": channel.proxy_url,
            }
            config.update(channel.extra)
            resolved.append((channel.source, config))
        return resolved


async def _run_collector_for_task(
    task_name: str,
    data_type: str,
    collector_map: dict[str, type[BaseCollector]],
    preferred_source: str | None,
    symbols: list[str] | None = None,
    extra_config: dict[str, Any] | None = None,
    **run_kwargs: Any,
) -> CollectResult:
    """解析渠道候选并带 fallback 地运行采集器。

    按优先级顺序尝试各候选：以 ``SUCCESS``/``PARTIAL``/``SKIPPED`` 结束的
    采集器胜出；``FAILED`` 或没有对应采集器的 source 则落入下一个候选。
    全部失败时返回最后一个结果，并附上每一次尝试的错误。

    ``SKIPPED`` 是采集器的主动判定（如非交易日、AI 内容已生成），视为终态
    而非渠道故障——否则单渠道任务（如 market-daily-review）的良性跳过会被
    强制改写为 FAILED 且丢失错误上下文。
    """
    candidates = await _resolve_task_channels(task_name, preferred_source)
    if not candidates:
        return _skipped_result("unknown", data_type)

    attempt_errors: list[str] = []
    last_result: CollectResult | None = None
    for source, channel_config in candidates:
        collector_class = collector_map.get(source)
        if collector_class is None:
            attempt_errors.append(
                f"[{source}] 渠道没有任务 {task_name} 对应的采集器"
            )
            continue

        config: dict[str, Any] = {
            "source": source,
            "data_type": data_type,
            **channel_config,
            **(extra_config or {}),
        }
        collector = collector_class(config)
        result = await collector.run(symbols=symbols, **run_kwargs)

        if result.status != CollectStatus.FAILED:
            if last_result is not None or attempt_errors:
                result.errors = attempt_errors + result.errors
            return result

        logger.info(
            "collector_fallback",
            task=task_name,
            from_source=source,
            status=result.status.value,
        )
        attempt_errors.extend(f"[{source}] {error}" for error in result.errors)
        last_result = result

    assert last_result is not None
    last_result.status = CollectStatus.FAILED
    last_result.errors = attempt_errors
    return last_result


def _load_collectors(spec: TaskSpec) -> dict[str, type[BaseCollector]]:
    """按声明的懒加载路径解析采集器类。"""
    collector_map: dict[str, type[BaseCollector]] = {}
    for source, path in spec.collectors.items():
        module_path, _, class_name = path.partition(":")
        module = importlib.import_module(module_path)
        collector_map[source] = getattr(module, class_name)
    return collector_map


def _make_task_entry(
    spec: TaskSpec,
) -> Callable[..., Awaitable[CollectResult]]:
    """由 TaskSpec 生成任务入口函数（签名兼容原手工入口）。"""

    async def entry(
        symbols: list[str] | None = None,
        preferred_source: str | None = None,
        **params: Any,
    ) -> CollectResult:
        resolved = {
            **spec.defaults,
            **{key: value for key, value in params.items() if value is not None},
        }
        data_type = (
            spec.data_type.format(**resolved)
            if "{" in spec.data_type
            else spec.data_type
        )
        extra_config = {key: resolved.get(key) for key in spec.config_params} or None

        run_kwargs: dict[str, Any] = {}
        for key in spec.run_params:
            value = resolved.get(key)
            converter = spec.converters.get(key)
            if converter is not None and value is not None:
                value = converter(value)
            run_kwargs[key] = value

        return await _run_collector_for_task(
            spec.name,
            data_type,
            _load_collectors(spec),
            preferred_source,
            symbols=symbols,
            extra_config=extra_config,
            **run_kwargs,
        )

    entry.__name__ = f"collect_{spec.name.replace('-', '_')}"
    entry.__doc__ = f"{spec.name} 采集任务入口（由 TaskSpec 生成）。"
    return entry


TASK_MAP: dict[str, Callable[..., Awaitable[CollectResult]]] = {
    name: _make_task_entry(spec) for name, spec in TASK_SPECS.items()
}
