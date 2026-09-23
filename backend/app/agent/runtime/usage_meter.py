"""模型调用计量 callback：预扣 → 结算 → 明细入队（arch/07 §3）。

挂在 ``build_langchain_model`` 的唯一出口上，助手多轮/单轮结构化/系统任务
全部覆盖；助手 agent 按用户缓存模型实例，同一 callback 实例会被并发共享，
因此以 run_id 维护 in-flight 状态，开始时捕获当次计量上下文（并发流各自正确）。

- ``on_chat_model_start``（chat 模型的开始事件；``on_llm_start`` 兜底，run_id 去重）：
  系统出口且有属主 → Redis 原子预扣；降级放行（``RESERVE_DEGRADED``）未真实
  预扣，跳过结算；不足仅告警并照常预扣计量——**LangChain callback manager
  会吞掉 callback 异常，raise 无法中断调用**，请求级拦截由 AI 入口的
  ``quota_service.precheck`` 显式承担（REST 429）；
- ``on_llm_end``：优先 usage_metadata 真实值，缺失走估算并标 ``estimated``；
  结算回补差额 + 明细入队；
- ``on_llm_error``：全额回补（失败调用不留用量记录）。

豁免路径（system 维度 / unlimited / BYOK）不查配额，仍记明细。
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import structlog
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

from app.agent.runtime.token_estimator import estimate_text_tokens
from app.core.config import get_settings
from app.services.quota import quota_service
from app.services.quota.constants import FEATURE_SYSTEM, OUTLET_SYSTEM
from app.services.quota.context import MeterContext, current_meter_context
from app.services.quota.usage_writer import UsageRecord, enqueue

logger = structlog.get_logger(__name__)

# in-flight 上限：超限清理 15 分钟前的陈旧项（取消的流不会触发 end 回调）
_MAX_INFLIGHT = 512
_STALE_SECONDS = 900.0


@dataclass
class _RunMeter:
    """单次 LLM 调用的预扣状态。"""

    ctx: MeterContext | None
    prompt_text: str
    reserved: int = 0
    started_at: float = field(default_factory=time.monotonic)


def _messages_text(messages: list[list[Any]]) -> str:
    """提取 chat 输入消息文本（on_chat_model_start 的嵌套消息列表）。"""
    parts: list[str] = []
    for batch in messages:
        for message in batch:
            content = getattr(message, "content", message)
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                parts.extend(
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                )
    return "\n".join(parts)


def _extract_usage(response: LLMResult) -> tuple[int, int] | None:
    """从 LLMResult 提取真实 (prompt, completion) tokens；缺失返回 None。"""
    try:
        generation = response.generations[0][0]
    except (IndexError, TypeError):
        return None
    message = getattr(generation, "message", None)
    usage = getattr(message, "usage_metadata", None)
    if isinstance(usage, dict) and usage.get("input_tokens") is not None:
        return int(usage["input_tokens"]), int(usage.get("output_tokens") or 0)
    llm_output = response.llm_output or {}
    token_usage = llm_output.get("token_usage") or llm_output.get("usage") or {}
    if token_usage and token_usage.get("prompt_tokens") is not None:
        return int(token_usage["prompt_tokens"]), int(token_usage.get("completion_tokens") or 0)
    return None


class UsageMeterCallback(AsyncCallbackHandler):
    """按模型实例构造（携带 outlet/provider/model_name），随模型缓存共享。"""

    def __init__(self, *, outlet: str, provider: str, model_name: str) -> None:
        self.outlet = outlet
        self.provider = provider
        self.model_name = model_name
        self._inflight: dict[uuid.UUID, _RunMeter] = {}

    async def _prune_stale(self) -> None:
        if len(self._inflight) < _MAX_INFLIGHT:
            return
        cutoff = time.monotonic() - _STALE_SECONDS
        for run_id in [k for k, v in self._inflight.items() if v.started_at < cutoff]:
            state = self._inflight.pop(run_id)
            # 陈旧项未结算：全额回补预扣后丢弃（取消的流不会触发 end 回调）
            if state.reserved and state.ctx is not None and state.ctx.user_id is not None:
                await quota_service.settle(state.ctx.user_id, state.reserved, 0)

    async def _start(
        self, run_id: uuid.UUID | None, prompt_text: str
    ) -> None:
        if run_id is None or run_id in self._inflight:
            return
        await self._prune_stale()
        raw_ctx = current_meter_context()
        # 未包裹 meter_scope 的调用（Celery 直调服务等）按系统维度记账，绝不漏计
        ctx = raw_ctx if raw_ctx is not None else MeterContext(user_id=None, feature=FEATURE_SYSTEM)
        reserved = 0
        if ctx.user_id is not None and self.outlet == OUTLET_SYSTEM:
            estimate = estimate_text_tokens(prompt_text) + (
                get_settings().quota_completion_reserve_tokens
            )
            remaining = await quota_service.check_and_reserve(ctx.user_id, estimate)
            if remaining == quota_service.RESERVE_DEGRADED:
                # Redis 降级 PG 放行未真实预扣：跳过结算——回补差额会在镜像恢复后虚增余额
                logger.warning(
                    "quota_gate_degraded_passthrough",
                    user_id=ctx.user_id,
                    feature=ctx.feature,
                    model=self.model_name,
                )
            else:
                if remaining == quota_service.RESERVE_DENIED:
                    # LangChain callback manager 会吞掉 callback 抛出的异常（仅打印
                    # "Error in ... callback"），raise 无法中断调用——此处不抛，照常
                    # 预扣与计量把镜像扣至负值；请求级拦截由入口 quota_service.precheck 承担
                    # （本 run 中途打穿的轮次是有限的放行窗口，下一个请求必被 precheck 拒）。
                    logger.warning(
                        "quota_exhausted_run_passthrough",
                        user_id=ctx.user_id,
                        feature=ctx.feature,
                        model=self.model_name,
                    )
                reserved = estimate
        self._inflight[run_id] = _RunMeter(ctx=ctx, prompt_text=prompt_text, reserved=reserved)

    async def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        await self._start(run_id, _messages_text(messages))

    async def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        # chat 模型不会同时触发两事件；兜底非 chat 调用（run_id 去重防双扣）
        await self._start(run_id, "\n".join(prompts))

    async def on_llm_end(self, response: LLMResult, *, run_id: uuid.UUID, **kwargs: Any) -> None:
        state = self._inflight.pop(run_id, None)
        if state is None or state.ctx is None:
            return
        usage = _extract_usage(response)
        if usage is not None:
            prompt_tokens, completion_tokens = usage
            estimated = False
        else:
            prompt_tokens = estimate_text_tokens(state.prompt_text)
            completion_text = getattr(response, "text", "") or ""
            completion_tokens = estimate_text_tokens(completion_text)
            estimated = True
        total = prompt_tokens + completion_tokens
        if state.reserved:
            await quota_service.settle(state.ctx.user_id or 0, state.reserved, total)
        enqueue(
            UsageRecord(
                user_id=state.ctx.user_id,
                feature=state.ctx.feature,
                model_name=self.model_name,
                provider=self.provider,
                outlet=self.outlet,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total,
                estimated=estimated,
                detail=state.ctx.detail,
            )
        )

    async def on_llm_error(
        self, error: BaseException, *, run_id: uuid.UUID, **kwargs: Any
    ) -> None:
        state = self._inflight.pop(run_id, None)
        if state is None:
            return
        # 失败调用全额回补，不留用量记录
        if state.reserved and state.ctx is not None and state.ctx.user_id is not None:
            await quota_service.settle(state.ctx.user_id, state.reserved, 0)
