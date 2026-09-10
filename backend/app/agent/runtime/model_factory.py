"""llm_config → LangChain 聊天模型实例工厂。

deepagents 助手循环与单轮结构化调用（``app.agent.runtime.structured``）共用。
"""

from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.core.config import get_settings
from app.services.admin.llm_config_service import ResolvedLLMConfig

# 助手回答含 thinking 块与工具结果整理，给足输出空间
ANTHROPIC_MAX_TOKENS = 8192


def build_langchain_model(
    cfg: ResolvedLLMConfig, *, disable_thinking: bool = False
) -> BaseChatModel:
    """把后台 LLM 配置转换为 LangChain 模型实例。

    Args:
        cfg: 已解密的默认 LLM 配置（llm_config 表）。
        disable_thinking: 显式关闭服务端 thinking（anthropic 协议端点默认开启，
            与 ``with_structured_output`` 的强制 tool_choice 冲突会 400）。
            助手循环需要 thinking 块，保持默认 False。

    Returns:
        protocol=anthropic（Kimi coding 等）→ ``ChatAnthropic``；
        protocol=openai（deepseek/zhipu/minimax 等兼容端点）→ ``ChatOpenAI``。
    """
    settings = get_settings()
    api_key = SecretStr(cfg.api_key)
    base_url = str(cfg.base_url) if cfg.base_url else None
    common: dict[str, Any] = {
        "timeout": settings.llm_http_read_timeout,
        "max_retries": settings.llm_max_retries,
    }
    if cfg.protocol == "anthropic":
        # ChatAnthropic 的 max_tokens 字段带 alias，静态签名不含该 kwarg，故解包传入
        params: dict[str, Any] = {
            "model": cfg.model_name,
            "api_key": api_key,
            "base_url": base_url,
            "max_tokens": ANTHROPIC_MAX_TOKENS,
            **common,
        }
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
        **common,
    )
