"""单轮结构化 LLM 调用统一封装。

财报/研报摘要与截图识别等单轮任务的公共路径：解析默认 LLM 配置 →
``build_langchain_model`` → ``with_structured_output``。输出 schema 即契约
（pydantic 模型），校验失败自动重试一次；仍失败则上抛 ``ValidationError``。
额度/限流类失败触发主备切换：主配置进冷却后重新解析（健康门切备用）
当次重试一次。多步任务走 deepagents 执行器（``app/agent/skills/*_agent.py``），
不要用本模块。
"""

import base64
from typing import Any, TypeVar, cast

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.runtime.model_factory import build_langchain_model
from app.services.admin.llm_config_service import (
    ResolvedLLMConfig,
    resolve_llm_by_id,
)
from app.services.admin.llm_failover import classify_llm_error, mark_unhealthy
from app.services.quota.user_llm_service import resolve_llm

T = TypeVar("T", bound=BaseModel)


def _image_block(data: bytes, media_type: str) -> dict[str, Any]:
    encoded = base64.b64encode(data).decode()
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{media_type};base64,{encoded}"},
    }


async def run_structured(
    session: AsyncSession,
    *,
    result_type: type[T],
    user_prompt: str,
    images: list[tuple[bytes, str]] | None = None,
    user_id: int | None = None,
    vision: bool = False,
    config_id: int | None = None,
) -> T:
    """执行单次结构化 LLM 调用并返回 pydantic 模型实例。

    Args:
        session: 数据库会话（用于解析 LLM 出口配置）。
        result_type: 输出 pydantic 模型，其 schema 即输出契约。
        user_prompt: 已渲染的任务提示词。
        images: 可选视觉输入 ``(bytes, media_type)`` 列表。
        user_id: 显式调用属主；缺省取当前计量上下文（页面入口包裹
            ``meter_scope`` 后自动按属主分流 BYOK，Celery 系统任务走系统默认）。
        vision: 无 BYOK 时解析视觉能力配置（截图识别路径）。
        config_id: 显式指定 llm_config 条目（F-KB 模型角色槽位路径），
            设置后忽略 ``user_id``/``vision`` 分流，走系统维度计量。

    Raises:
        ValidationError: 模型输出不符合 schema（重试一次后仍失败）。
    """
    if config_id is not None:
        cfg = await resolve_llm_by_id(session, config_id)
    else:
        cfg, _outlet = await resolve_llm(session, user_id, vision=vision)

    content: Any = user_prompt
    if images:
        content = [
            {"type": "text", "text": user_prompt},
            *(_image_block(data, media_type) for data, media_type in images),
        ]
    message = HumanMessage(content=content)

    def _output_methods(protocol: str) -> tuple[str, ...]:
        """按协议给出结构化输出法（首选 + 兜底）。

        anthropic 协议端点（kimi coding 等）2026-09-08 起对强制 tool_choice
        间歇性忽略，function_calling 法会静默拿到 None，故 json_schema（原生
        output_format）优先；但 MiniMax 等兼容端点不实现 output_format，会
        忽略并返回纯文本（OutputParserException），tool calling 反而可靠
        （批次 5 对话实测）——json_schema 失败后换 function_calling 兜底。
        openai 协议一律 function_calling。
        """
        if protocol == "anthropic":
            return ("json_schema", "function_calling")
        return ("function_calling",)

    async def _invoke_method(current: ResolvedLLMConfig, method: str) -> T:
        model = build_langchain_model(current, disable_thinking=True)
        structured = model.with_structured_output(result_type, method=method)
        result = await structured.ainvoke([message])
        if result is None:
            # tool_choice 被端点忽略时静默拿 None（kimi/MiniMax 实测），
            # 转为解析失败以触发兜底法重试，而非把 None 当合法结果上抛
            raise OutputParserException("模型未返回结构化输出（tool call 缺失）")
        return cast(T, result)

    async def _invoke(current: ResolvedLLMConfig) -> T:
        methods = _output_methods(current.protocol)
        # 首选法解析失败时按兜底序换法重试一次；无兜底法则同法重试
        fallback = methods[1] if len(methods) > 1 else methods[0]
        try:
            return await _invoke_method(current, methods[0])
        except (ValidationError, OutputParserException):
            return await _invoke_method(current, fallback)

    try:
        return await _invoke(cfg)
    except Exception as exc:
        if not classify_llm_error(exc):
            raise
        # 额度/限流类失败：主配置进冷却（callback 已标记，此处确定性补一次），
        # 重新解析过健康门切备用后当次重试；无备用可切则原样上抛，
        # 避免对同一死模型重复烧 SDK 退避时间
        await mark_unhealthy(cfg.config_id)
        if config_id is not None:
            retried = await resolve_llm_by_id(session, config_id)
        else:
            retried, _outlet = await resolve_llm(session, user_id, vision=vision)
        if retried.config_id == cfg.config_id:
            raise
        return await _invoke(retried)
