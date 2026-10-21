"""单轮结构化 LLM 调用统一封装。

财报/研报摘要与截图识别等单轮任务的公共路径：解析默认 LLM 配置 →
``build_langchain_model`` → ``with_structured_output``。输出 schema 即契约
（pydantic 模型），解析失败按方法兜底序换法重试一次；仍失败则上抛。
额度/限流类失败触发主备切换：主配置进冷却后重新解析（健康门切备用）
当次重试一次。端点强制 adaptive thinking（MiniMax M3.1 起实测）时
省略 thinking 参数自愈重试，且自愈后同样参与方法兜底；thinking 不可关
时放大输出预算（与 thinking 共享）。多步任务走 deepagents 执行器
（``app/agent/skills/*_agent.py``），不要用本模块。
"""

import base64
import time
from typing import Any, TypeVar, cast

import structlog
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
from app.services.admin.llm_task_binding_service import resolve_task_config_id
from app.services.quota.user_llm_service import resolve_llm

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

# 已观测到「强制 adaptive thinking」约束的端点（(config_id, model_name) 键，
# 进程内记忆）：首次 400 探测后记住，后续调用直接省略 thinking 参数，
# 不再对同一端点重复烧失败请求。服务端解除约束不会自动移除（影响仅多传一个
# 被忽略的参数级别，重启即恢复探测）。
_THINKING_REQUIRED_ENDPOINTS: set[tuple[int, str]] = set()

# thinking 不可关的端点：thinking 与输出共享 max_tokens 预算，长思考可烧满
# 助手循环的默认预算致空文本（MiniMax M3.1-Flash 实测），结构化调用给足余量
STRUCTURED_THINKING_MAX_TOKENS = 32768


def _is_thinking_required_error(exc: BaseException) -> bool:
    """识别「模型强制 thinking」类 400（MiniMax M3.1-Flash 起实测，错误码 2013）。"""
    if getattr(exc, "status_code", None) != 400:
        return False
    return "adaptive thinking" in str(exc).lower()


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
    task_key: str | None = None,
    meta_out: dict[str, Any] | None = None,
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
        task_key: 任务槽位键（AI 任务级模型分配）。``config_id`` 未显式给出时
            按 ``llm_task_binding`` 解析绑定条目——命中则等价于传入该条目
            config_id（忽略 BYOK 分流，主备按绑定条目自身链切换），
            未绑定走既有默认路径。
        meta_out: 调用元信息回填容器（可选）。成功后写入
            ``latency_ms``/``model_name``/``method``/``failover``，供调用方
            落观测（agent_run llm step、ai_analysis_result 补全等）。

    Raises:
        ValidationError: 模型输出不符合 schema（重试一次后仍失败）。
    """
    if config_id is None and task_key is not None:
        config_id = await resolve_task_config_id(session, task_key)
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

    async def _invoke_method(
        current: ResolvedLLMConfig, method: str, *, disable_thinking: bool
    ) -> T:
        # thinking 与输出共享 max_tokens 预算：不可关 thinking 的端点须放大预算，
        # 否则长思考烧满默认值导致空文本（MiniMax M3.1-Flash 实测）
        max_tokens = None if disable_thinking else STRUCTURED_THINKING_MAX_TOKENS
        model = build_langchain_model(
            current, disable_thinking=disable_thinking, max_tokens=max_tokens
        )
        structured = model.with_structured_output(result_type, method=method)
        result = await structured.ainvoke([message])
        if result is None:
            # tool_choice 被端点忽略时静默拿 None（kimi/MiniMax 实测），
            # 转为解析失败以触发兜底法重试，而非把 None 当合法结果上抛
            raise OutputParserException("模型未返回结构化输出（tool call 缺失）")
        return cast(T, result)

    async def _invoke(current: ResolvedLLMConfig) -> T:
        endpoint = (current.config_id, current.model_name)
        methods = _output_methods(current.protocol)
        # 首选法解析失败时按兜底序换法重试一次；无兜底法则同法重试
        fallback = methods[1] if len(methods) > 1 else methods[0]

        async def _try_method(method: str) -> T:
            """单法调用；遇「强制 thinking」400 记住端点并省略参数自愈重试一次。"""
            disable_thinking = endpoint not in _THINKING_REQUIRED_ENDPOINTS
            try:
                result = await _invoke_method(current, method, disable_thinking=disable_thinking)
            except Exception as exc:
                if not (disable_thinking and _is_thinking_required_error(exc)):
                    raise
                # 端点强制 adaptive thinking（MiniMax M3.1-Flash 起，2026-10-20
                # 服务端升级实锤）：显式 disabled 400，省略 thinking 参数后可用。
                # 记住端点自愈，避免每轮重复烧失败请求。
                _THINKING_REQUIRED_ENDPOINTS.add(endpoint)
                logger.warning(
                    "structured_endpoint_requires_thinking",
                    config_id=current.config_id,
                    model_name=current.model_name,
                    method=method,
                )
                return await _try_method(method)
            _meta["method"] = method
            return result

        try:
            return await _try_method(methods[0])
        except (ValidationError, OutputParserException):
            return await _try_method(fallback)

    _meta: dict[str, str] = {}
    t0 = time.monotonic()
    failover = False
    try:
        result = await _invoke(cfg)
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
        failover = True
        final_cfg = retried
        result = await _invoke(retried)
    else:
        final_cfg = cfg
    if meta_out is not None:
        meta_out["latency_ms"] = int((time.monotonic() - t0) * 1000)
        meta_out["model_name"] = final_cfg.model_name
        meta_out["method"] = _meta.get("method")
        meta_out["failover"] = failover
    return result
