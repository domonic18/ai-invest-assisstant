"""单轮结构化 LLM 调用统一封装。

财报/研报摘要与截图识别等单轮任务的公共路径：解析默认 LLM 配置 →
``build_langchain_model`` → ``with_structured_output``。输出 schema 即契约
（pydantic 模型），解析失败按方法兜底序换法重试一次；schema 校验失败时
把校验错误回喂让模型改一次；仍失败则上抛。
额度/连接类失败触发主备切换：主配置进冷却（分档 TTL）后重跑同一入口
解析（健康门切备用）当次重试一次。端点强制 adaptive thinking（MiniMax
M3.1 起实测）时省略 thinking 参数自愈重试，且自愈后同样参与方法兜底；
thinking 不可关时放大输出预算（与 thinking 共享）。多步任务走 deepagents
执行器（``app/agent/skills/*_agent.py``），不要用本模块。
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
from app.services.admin.llm_task_binding_service import resolve_task_llm
from app.services.quota.user_llm_service import resolve_llm

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

# 已观测到「强制 adaptive thinking」约束的端点（(config_id, model_name) 键，
# 进程内记忆）：首次 400 探测后记住，后续调用直接省略 thinking 参数，
# 不再对同一端点重复烧失败请求。服务端解除约束不会自动移除（影响仅多传一个
# 被忽略的参数级别，重启即恢复探测）。
_THINKING_REQUIRED_ENDPOINTS: set[tuple[int, str]] = set()

# thinking 不可关的端点：thinking 与输出共享 max_tokens 预算，长思考可烧满
# 助手循环的默认预算致空文本（MiniMax M3.1-Flash 实测），结构化调用给足余量。
# 32768 实测仍会被 Minimax 的长思考烧满致「不吐 tool call」，故提到 65536。
STRUCTURED_THINKING_MAX_TOKENS = 65536

# 端点 → 实际生效的结构化输出法（进程内记忆）。anthropic 协议端点对两种
# 方法的支持度不一致：kimi coding 忽略强制 tool_choice（function_calling
# 拿不到 tool call），Minimax 强制 adaptive thinking 时 json_schema 烧满
# 预算不吐 tool call（2026-11-06 生产实测）。按端点记住上次生效的方法，
# 后续优先走它，避免每次都先撞一次失败法。
_ENDPOINT_PREFERRED_METHOD: dict[tuple[int, str], str] = {}

# 校验失败修复时回喂给模型的错误摘要长度上限
_REPAIR_ERROR_MAX_CHARS = 2000


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


def _repair_message(base: HumanMessage, exc: ValidationError) -> HumanMessage:
    """构造修复提示：把 schema 校验错误回喂给模型。

    Args:
        base: 原始提示消息。
        exc: 模型输出的校验错误。

    Returns:
        追加了错误摘要的新提示消息。
    """
    detail = str(exc)[:_REPAIR_ERROR_MAX_CHARS]
    hint = (
        "\n\n上一次输出未通过 schema 校验，请按下列错误修正后重新输出结构化结果：\n"
        f"{detail}"
    )
    content = base.content
    if isinstance(content, str):
        return HumanMessage(content=content + hint)
    return HumanMessage(content=[*content, {"type": "text", "text": hint}])


async def run_structured(
    session: AsyncSession,
    *,
    result_type: type[T],
    user_prompt: str,
    images: list[tuple[bytes, str]] | None = None,
    user_id: int | None = None,
    vision: bool = False,
    config_id: int | None = None,
    backup_config_id: int | None = None,
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
        backup_config_id: 显式主条目的备用引用（与 ``config_id`` 配对，
            携带选择点的主备语义进健康门与重试路径）。
        task_key: 任务槽位键（AI 任务级模型分配）。优先于 ``config_id``：
            经 ``resolve_task_llm`` 解析槽位主备绑定（命中即等价于显式
            引用，忽略 BYOK 分流），主备皆不可用时 fail loud。
        meta_out: 调用元信息回填容器（可选）。成功后写入
            ``latency_ms``/``model_name``/``method``/``failover``，供调用方
            落观测（agent_run llm step、ai_analysis_result 补全等）。

    Raises:
        ValidationError: 模型输出不符合 schema（回喂校验错误修复一次后仍失败）。
    """
    if task_key is not None:
        cfg = await resolve_task_llm(session, task_key)
    elif config_id is not None:
        cfg = await resolve_llm_by_id(
            session, config_id, backup_config_id=backup_config_id
        )
    else:
        cfg, _outlet = await resolve_llm(session, user_id, vision=vision)

    content: Any = user_prompt
    if images:
        content = [
            {"type": "text", "text": user_prompt},
            *(_image_block(data, media_type) for data, media_type in images),
        ]
    message = HumanMessage(content=content)

    def _output_methods(protocol: str, endpoint: tuple[int, str]) -> tuple[str, ...]:
        """按协议与端点记忆给出结构化输出法（首选 + 兜底）。

        anthropic 协议端点对两种方法的支持度不一致：kimi coding 忽略强制
        tool_choice（function_calling 静默拿不到 tool call），而 Minimax 等
        强制 adaptive thinking 的端点在 json_schema 下会烧满输出预算不吐
        tool call（2026-11-06 生产实测）——故默认 function_calling 优先，
        并记住该端点实际生效的方法，后续优先走它。openai 协议一律
        function_calling。
        """
        if protocol != "anthropic":
            return ("function_calling",)
        preferred = _ENDPOINT_PREFERRED_METHOD.get(endpoint)
        if preferred:
            others = tuple(m for m in ("json_schema", "function_calling") if m != preferred)
            return (preferred, *others)
        return ("function_calling", "json_schema")

    async def _invoke_method(
        current: ResolvedLLMConfig,
        method: str,
        *,
        disable_thinking: bool,
        msg: HumanMessage,
    ) -> T:
        # thinking 与输出共享 max_tokens 预算：不可关 thinking 的端点须放大预算，
        # 否则长思考烧满默认值导致空文本（MiniMax M3.1-Flash 实测）
        max_tokens = None if disable_thinking else STRUCTURED_THINKING_MAX_TOKENS
        model = build_langchain_model(
            current, disable_thinking=disable_thinking, max_tokens=max_tokens
        )
        structured = model.with_structured_output(result_type, method=method)
        result = await structured.ainvoke([msg])
        if result is None:
            # tool_choice 被端点忽略时静默拿 None（kimi/MiniMax 实测），
            # 转为解析失败以触发兜底法重试，而非把 None 当合法结果上抛
            raise OutputParserException("模型未返回结构化输出（tool call 缺失）")
        return cast(T, result)

    async def _invoke(current: ResolvedLLMConfig) -> T:
        endpoint = (current.config_id, current.model_name)
        methods = _output_methods(current.protocol, endpoint)
        # 首选法解析失败时按兜底序换法重试一次；无兜底法则同法重试
        fallback = methods[1] if len(methods) > 1 else methods[0]

        async def _try_method(method: str, msg: HumanMessage) -> T:
            """单法调用；遇「强制 thinking」400 记住端点并省略参数自愈重试一次。"""
            disable_thinking = endpoint not in _THINKING_REQUIRED_ENDPOINTS
            try:
                result = await _invoke_method(
                    current, method, disable_thinking=disable_thinking, msg=msg
                )
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
                return await _try_method(method, msg)
            _meta["method"] = method
            if current.protocol == "anthropic":
                # 记住该端点实际生效的方法，下次优先走它
                _ENDPOINT_PREFERRED_METHOD[endpoint] = method
            return result

        try:
            return await _try_method(methods[0], message)
        except ValidationError as exc:
            # 结构有但字段不合（缺必填字段/类型不符）：把校验错误回喂给模型改一次
            return await _try_method(methods[0], _repair_message(message, exc))
        except OutputParserException:
            pass

        # 首选法没拿到结构化结果：换兜底法
        try:
            return await _try_method(fallback, message)
        except ValidationError as exc:
            return await _try_method(fallback, _repair_message(message, exc))

    _meta: dict[str, str] = {}
    t0 = time.monotonic()
    failover = False
    try:
        result = await _invoke(cfg)
    except Exception as exc:
        failure_class = classify_llm_error(exc)
        if failure_class is None:
            raise
        # 额度/连接类失败：主配置进冷却（callback 已标记，此处确定性补一次），
        # 重跑同一入口解析过健康门切备用后当次重试；无备用可切则原样上抛，
        # 避免对同一死模型重复烧 SDK 退避时间
        await mark_unhealthy(cfg.config_id, failure_class=failure_class)
        if task_key is not None:
            retried = await resolve_task_llm(session, task_key)
        elif config_id is not None:
            retried = await resolve_llm_by_id(
                session, config_id, backup_config_id=backup_config_id
            )
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
