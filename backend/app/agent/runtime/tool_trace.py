"""技能执行器工具调用留痕 callback。

挂在 ``app.agent.skills.skill_runtime.invoke`` 的共享调用入口上，
deepagents 技能 agent（大盘复盘/个股分析/涨停复盘等）的工具循环统一
留痕。事件走 structlog（snake_case 事件 + kwargs 字段），celery 定时
路径经 contextvars 自动携带 task_run_id，无需在此透传。

工具名取自 ``serialized["name"]``（on_tool_end 不回传工具名），起点以
run_id 键控计时；取消的流不会触发 end 回调，陈旧项按上限清理。
"""

import time
import uuid
from typing import Any

import structlog
from langchain_core.callbacks import AsyncCallbackHandler

logger = structlog.get_logger(__name__)

# in-flight 上限：超限清理 15 分钟前的陈旧项（取消的流不会触发 end 回调）
_MAX_INFLIGHT = 512
_STALE_SECONDS = 900.0
_SUMMARY_CHARS = 120


class ToolTraceCallback(AsyncCallbackHandler):
    """模块单例（``TOOL_TRACE``）并发共享，状态仅 run_id 键控的计时。"""

    def __init__(self) -> None:
        self._starts: dict[uuid.UUID, tuple[str, float]] = {}

    async def _prune_stale(self) -> None:
        if len(self._starts) < _MAX_INFLIGHT:
            return
        cutoff = time.monotonic() - _STALE_SECONDS
        for run_id in [k for k, v in self._starts.items() if v[1] < cutoff]:
            self._starts.pop(run_id, None)

    async def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: uuid.UUID,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        if run_id in self._starts:
            return
        await self._prune_stale()
        tool = str(serialized.get("name") or "unknown")
        self._starts[run_id] = (tool, time.monotonic())
        logger.info(
            "agent_tool_call",
            tool=tool,
            phase="start",
            args_summary=str(inputs if inputs is not None else input_str)[
                :_SUMMARY_CHARS
            ],
        )

    async def on_tool_end(
        self, output: Any, *, run_id: uuid.UUID, **kwargs: Any
    ) -> None:
        state = self._starts.pop(run_id, None)
        if state is None:
            return
        tool, started = state
        logger.info(
            "agent_tool_call",
            tool=tool,
            phase="end",
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    async def on_tool_error(
        self, error: BaseException, *, run_id: uuid.UUID, **kwargs: Any
    ) -> None:
        state = self._starts.pop(run_id, None)
        if state is None:
            return
        tool, started = state
        logger.warning(
            "agent_tool_call",
            tool=tool,
            phase="error",
            duration_ms=int((time.monotonic() - started) * 1000),
            error=str(error)[:_SUMMARY_CHARS],
        )


TOOL_TRACE = ToolTraceCallback()
