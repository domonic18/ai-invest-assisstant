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
from app.services.quota.constants import OUTLET_BYOK, OUTLET_SYSTEM
from app.utils.api_base import normalize_api_base

# 助手回答含 thinking 块与工具结果整理，给足输出空间
ANTHROPIC_MAX_TOKENS = 8192


def build_langchain_model(
    cfg: ResolvedLLMConfig, *, disable_thinking: bool = False, meter: bool = True
) -> BaseChatModel:
    """把 LLM 配置（系统或 BYOK）转换为 LangChain 模型实例。

    Args:
        cfg: 已解密的 LLM 配置（llm_config 表或用户自备 Key）。
        disable_thinking: 显式关闭服务端 thinking（anthropic 协议端点默认开启，
            与 ``with_structured_output`` 的强制 tool_choice 冲突会 400）。
            助手循环需要 thinking 块，保持默认 False。
        meter: 挂载用量计量 callback（测试注入 fake 模型时可关闭）。

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
    if cfg.protocol == "anthropic":
        # ChatAnthropic 的 max_tokens/timeout 字段带 alias，静态签名不含该
        # kwarg，故解包传入。其 timeout 字段类型仅收 float（httpx.Timeout 会被
        # pydantic 拒收），connect 分离不可行——读超时兜底 + 任务级软硬限覆盖
        params: dict[str, Any] = {
            "model": cfg.model_name,
            "api_key": api_key,
            "base_url": base_url,
            "max_tokens": ANTHROPIC_MAX_TOKENS,
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
    extra_body: dict[str, Any] = (
        {"thinking": {"type": "disabled"}} if disable_thinking else {}
    )
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
