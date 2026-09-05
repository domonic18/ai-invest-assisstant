"""Agent runtime: Skill 执行器与共享样板。

提供 ``run_structured_agent`` / ``run_structured_agent_with_metrics`` 抹平 5 个
AI service 中重复的 ``resolve_default_llm + build_model_config + build_agent +
agent.run`` 模板，后者附带 perf_counter 延迟测量。
"""

from typing import Any, TypeVar, cast

from pydantic_ai import BinaryContent
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.core.llm_router import build_agent
from app.services.admin.llm_config_service import resolve_default_llm

T = TypeVar("T")


async def run_structured_agent(
    session: AsyncSession,
    *,
    prompt_config: Any,
    user_prompt: str,
    result_type: type[T],
    images: list[BinaryContent] | None = None,
) -> T:
    """统一执行结构化 LLM 调用并返回反序列化后的 BaseModel 实例。

    适用于无需测延迟的简单 Skill（如 financial/research summary）。
    ``images`` 非空时消息以 [文本, *图片] 列表发送（视觉识别类 Skill）。
    """
    resolved = await resolve_default_llm(session)
    model_config = {
        "provider": resolved.provider,
        "model": resolved.model_name,
        "api_key": resolved.api_key,
        "base_url": resolved.base_url,
    }
    agent = build_agent(
        prompt_config=prompt_config,
        model_config=model_config,
        result_type=result_type,
    )
    message: Any = [user_prompt, *images] if images else user_prompt
    async with agent:
        result = await agent.run(message)
    return cast(T, result.output)


async def run_structured_agent_with_metrics(
    session: AsyncSession,
    *,
    prompt_config: Any,
    user_prompt: str,
    result_type: type[T],
    images: list[BinaryContent] | None = None,
) -> tuple[T, int, str]:
    """带 perf_counter 延迟测量的执行入口。

    Returns:
        (output, latency_ms, model_name) — model_name 形如
        ``"anthropic/claude-sonnet-4"``，便于落库 ``ai_analysis_result.model``。
    """
    import time

    resolved = await resolve_default_llm(session)
    model_config = {
        "provider": resolved.provider,
        "model": resolved.model_name,
        "api_key": resolved.api_key,
        "base_url": resolved.base_url,
    }
    agent = build_agent(
        prompt_config=prompt_config,
        model_config=model_config,
        result_type=result_type,
    )

    message: Any = [user_prompt, *images] if images else user_prompt
    started = time.perf_counter()
    async with agent:
        result = await agent.run(message)
    latency_ms = int((time.perf_counter() - started) * 1000)
    output = cast(T, result.output)
    model_name = f"{resolved.provider}/{resolved.model_name}"
    return output, latency_ms, model_name
