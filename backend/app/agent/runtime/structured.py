"""单轮结构化 LLM 调用统一封装。

财报/研报摘要与截图识别等单轮任务的公共路径：解析默认 LLM 配置 →
``build_langchain_model`` → ``with_structured_output``。输出 schema 即契约
（pydantic 模型），校验失败自动重试一次；仍失败则上抛 ``ValidationError``。
多步任务走 deepagents 执行器（``app/agent/skills/*_agent.py``），不要用本模块。
"""

import base64
from typing import Any, TypeVar, cast

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.runtime.model_factory import build_langchain_model
from app.services.admin.llm_config_service import resolve_default_llm

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
) -> T:
    """执行单次结构化 LLM 调用并返回 pydantic 模型实例。

    Args:
        session: 数据库会话（用于解析默认 LLM 配置）。
        result_type: 输出 pydantic 模型，其 schema 即输出契约。
        user_prompt: 已渲染的任务提示词。
        images: 可选视觉输入 ``(bytes, media_type)`` 列表。

    Raises:
        ValidationError: 模型输出不符合 schema（重试一次后仍失败）。
    """
    cfg = await resolve_default_llm(session)
    structured = build_langchain_model(cfg).with_structured_output(result_type)

    content: Any = user_prompt
    if images:
        content = [
            {"type": "text", "text": user_prompt},
            *(_image_block(data, media_type) for data, media_type in images),
        ]
    message = HumanMessage(content=content)

    try:
        return cast(T, await structured.ainvoke([message]))
    except ValidationError:
        # 输出不符合 schema 时重试一次
        return cast(T, await structured.ainvoke([message]))
