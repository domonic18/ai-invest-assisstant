"""渠道×数据类型调试服务：对单个渠道强制执行一次只采集不落库的试跑。

与正式采集链路（runner.run_task → fallback → store → collector_log）的区别：
- 单渠道强制，不做渠道 fallback；
- 只调用 ``collector.collect``，跳过 store 与 collector_log；
- 全程受 ``settings.collector_debug_timeout_seconds`` 超时约束；
- 响应只含样例数据与计数，绝不回传渠道凭据。
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any, Literal, cast

import structlog
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.schemas.collector import (
    CollectorChannelDebugRequest,
    CollectorChannelDebugResponse,
)
from app.services.admin.collector_channels import (
    CollectorChannelConfigService,
    resolve_collector_channel,
)

logger = structlog.get_logger(__name__)

_SAMPLE_LIMIT = 3


class CollectorDebugService:
    """面向管理后台的采集渠道调试服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def debug_channel(
        self, config_id: int, req: CollectorChannelDebugRequest
    ) -> CollectorChannelDebugResponse:
        """对 ``config_id`` 渠道试跑 ``req.dataType`` 任务，返回样例与计数。

        所有失败均折叠为 ``ok=false`` + 分类错误（不打断管理端交互），
        与服务状态探测的降级风格一致。
        """
        started = time.perf_counter()
        service = CollectorChannelConfigService(self.session)
        config = await service.repo.get(config_id)
        if config is None:
            return self._failure("disabled", f"渠道配置 {config_id} 不存在")
        if not config.is_enabled:
            return self._failure("disabled", "渠道已禁用，请先启用再调试")
        source = config.source

        # 函数内导入：collector 运行时与 app 服务层保持既定边界
        from collector.runtime.registry import TASK_SPECS

        spec = TASK_SPECS.get(req.data_type)
        if spec is None:
            return self._failure("no_collector", f"未注册的采集任务类型: {req.data_type}")
        if source not in spec.collectors:
            return self._failure(
                "no_collector", f"渠道 {source} 未声明任务 {req.data_type} 的采集器"
            )

        channel_config = await resolve_collector_channel(self.session, source)
        if channel_config is None:
            return self._failure(
                "disabled", "渠道配置无法解析（API Key 解密失败）"
            )

        try:
            collector, collect_kwargs = self._build_collect_call(
                spec, source, channel_config, req
            )
        except Exception as exc:  # noqa: BLE001
            return self._failure("error", f"参数解析失败: {exc}")

        timeout = get_settings().collector_debug_timeout_seconds
        try:
            raw = await asyncio.wait_for(collect_kwargs(collector), timeout=timeout)
        except asyncio.TimeoutError:
            return self._failure("timeout", f"采集超时（>{timeout:.0f}s），可在设置中调整上限")
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "collector_debug_failed",
                source=source,
                data_type=req.data_type,
                error=str(exc),
            )
            return self._failure("error", str(exc) or type(exc).__name__)

        items = list(raw or [])
        sample = items[:_SAMPLE_LIMIT]
        sample_valid = 0
        for item in sample:
            try:
                standardized = await collector.transform(item)
                if await collector.validate(standardized):
                    sample_valid += 1
            except Exception:  # noqa: BLE001
                pass

        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "collector_debug_finished",
            source=source,
            data_type=req.data_type,
            collected=len(items),
            duration_ms=duration_ms,
        )
        return CollectorChannelDebugResponse(
            ok=True,
            duration_ms=duration_ms,
            collected=len(items),
            sample_valid=sample_valid,
            sample_items=[jsonable_encoder(item) for item in sample],
        )

    def _build_collect_call(
        self,
        spec: Any,
        source: str,
        channel_config: dict[str, Any],
        req: CollectorChannelDebugRequest,
    ) -> tuple[Any, Callable[[Any], Awaitable[list[dict[str, Any]]]]]:
        """镜像 ``registry._run_collector_for_task`` 的 config/kwargs 组装。

        返回 ``(采集器实例, collect 调用协程工厂)``。
        """
        from collector.runtime.registry import _load_collectors

        resolved: dict[str, Any] = {
            **spec.defaults,
            **{k: v for k, v in req.params.items() if v is not None},
        }
        data_type = (
            spec.data_type.format(**resolved)
            if "{" in spec.data_type
            else spec.data_type
        )
        extra_config = {key: resolved.get(key) for key in spec.config_params}

        run_kwargs: dict[str, Any] = {}
        for key in spec.run_params:
            value = resolved.get(key)
            converter = spec.converters.get(key)
            if converter is not None and value is not None:
                value = converter(value)
            run_kwargs[key] = value

        collector_class = _load_collectors(spec)[source]
        collector = collector_class(
            {
                "source": source,
                "data_type": data_type,
                **channel_config,
                **extra_config,
            }
        )
        return collector, cast(
            Callable[[Any], Awaitable[list[dict[str, Any]]]],
            lambda c: c.collect(symbols=req.symbols, **run_kwargs),
        )

    @staticmethod
    def _failure(
        error_kind: Literal["no_collector", "disabled", "timeout", "error"],
        error: str,
    ) -> CollectorChannelDebugResponse:
        """构造折叠后的失败响应。"""
        return CollectorChannelDebugResponse(ok=False, error_kind=error_kind, error=error)
