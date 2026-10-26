"""llm_config → LangChain 聊天模型实例工厂。

deepagents 助手循环与单轮结构化调用（``app.agent.runtime.structured``）共用。
全部模型实例的唯一产地：计量与配额拦截（``UsageMeterCallback``）在此挂载，
三个调用入口（助手 SSE / 页面单轮与 skill / Celery 系统任务）自然全覆盖。
"""

from typing import Any

import httpx
from langchain_anthropic import ChatAnthropic
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.agent.runtime.usage_meter import UsageMeterCallback
from app.core.config import get_settings
from app.services.admin.llm_config_service import ResolvedLLMConfig
from app.services.admin.llm_failover import FailoverHealthCallback
from app.services.quota.constants import OUTLET_BYOK, OUTLET_SYSTEM
from app.utils.api_base import normalize_api_base

# thinking 模型（kimi k3.1-pro 等）每轮调用 thinking 与输出共享该预算，
# 8192 会被长思考精确烧满，最终回复截断致 skill 的 JSON 解析失败
# （2026-10-26 复盘事故：主调用与重试 completion_tokens 均=8192）。
# 与 structured 的 STRUCTURED_THINKING_MAX_TOKENS 同档；max_tokens 只是
# 上限不产生额外费用，k3.1-pro 1M 上下文量级下该值无端点约束风险
ANTHROPIC_MAX_TOKENS = 32768


def build_langchain_model(
    cfg: ResolvedLLMConfig,
    *,
    disable_thinking: bool = False,
    meter: bool = True,
    max_tokens: int | None = None,
) -> BaseChatModel:
    """把 LLM 配置（系统或 BYOK）转换为 LangChain 模型实例。

    Args:
        cfg: 已解密的 LLM 配置（llm_config 表或用户自备 Key）。
        disable_thinking: 显式关闭服务端 thinking（anthropic 协议端点默认开启，
            与 ``with_structured_output`` 的强制 tool_choice 冲突会 400）。
            助手循环需要 thinking 块，保持默认 False。强制 adaptive thinking
            的端点（MiniMax M3.1 起实测）会拒绝该参数——由 ``structured``
            捕获 400 后按 disable_thinking=False 自愈重试。
        meter: 挂载用量计量 callback（测试注入 fake 模型时可关闭）。
        max_tokens: anthropic 协议输出预算覆盖；缺省 ``ANTHROPIC_MAX_TOKENS``。
            thinking 与输出共享该预算，预算过小会被长思考烧满导致空文本/
            截断（MiniMax M3.1-Flash、kimi k3.1-pro 实测），故默认即给足。

    Returns:
        protocol=anthropic（Kimi coding 等）→ ``ChatAnthropic``；
        protocol=openai（deepseek/zhipu/minimax 等兼容端点）→ ``ChatOpenAI``。
    """
    settings = get_settings()
    api_key = SecretStr(cfg.api_key)
    # SDK 会自行拼接端点路径，粘贴了完整端点的 base_url 须先归一化
    base_url = normalize_api_base(str(cfg.base_url)) if cfg.base_url else None
    # connect 与 read 分离：建连黑洞不应拖满读超时
    openai_timeout = httpx.Timeout(
        connect=settings.llm_http_connect_timeout,
        read=settings.llm_http_read_timeout,
        write=120.0,
        pool=10.0,
    )
    callbacks: list[BaseCallbackHandler] = []
    if meter:
        callbacks.append(
            UsageMeterCallback(
                outlet=OUTLET_BYOK if cfg.provider == "byok" else OUTLET_SYSTEM,
                provider=cfg.provider,
                model_name=cfg.model_name,
            )
        )
        # 主备切换：额度耗尽类错误标记配置进入冷却（BYOK 负数哨兵 id 内部已忽略）
        if cfg.config_id > 0:
            callbacks.append(FailoverHealthCallback(cfg.config_id))
    if cfg.protocol == "anthropic":
        # ChatAnthropic 的 max_tokens/timeout 字段带 alias，静态签名不含该
        # kwarg，故解包传入。其 timeout 字段类型仅收 float（httpx.Timeout 会被
        # pydantic 拒收），connect 分离不可行——读超时兜底 + 任务级软硬限覆盖
        params: dict[str, Any] = {
            "model": cfg.model_name,
            "api_key": api_key,
            "base_url": base_url,
            "max_tokens": max_tokens or ANTHROPIC_MAX_TOKENS,
            "timeout": settings.llm_http_read_timeout,
            "max_retries": settings.llm_max_retries,
        }
        if callbacks:
            params["callbacks"] = callbacks
        if disable_thinking:
            params["thinking"] = {"type": "disabled"}
        return ChatAnthropic(**params)
    # OpenAI 兼容端点的 thinking 开关方言（deepseek v4 等实测）：顶层 thinking 对象。
    # 结构化输出的强制 tool_choice 与 thinking 模式互斥，须显式关闭。
    extra_body: dict[str, Any] = {"thinking": {"type": "disabled"}} if disable_thinking else {}
    return ChatOpenAI(
        model=cfg.model_name,
        api_key=api_key,
        base_url=base_url,
        extra_body=extra_body,
        stream_usage=meter,  # 流式拿到真实 usage 的前提（不计量时保持端点默认）
        timeout=openai_timeout,
        max_retries=settings.llm_max_retries,
        callbacks=callbacks,
    )
