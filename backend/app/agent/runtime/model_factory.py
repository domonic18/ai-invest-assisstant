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


def build_langchain_model(cfg: ResolvedLLMConfig) -> BaseChatModel:
    """把后台 LLM 配置转换为 LangChain 模型实例。

    Args:
        cfg: 已解密的默认 LLM 配置（llm_config 表）。

    Returns:
        anthropic 协议（含 Kimi coding 端点）→ ``ChatAnthropic``；
        其余 provider（deepseek/zhipu/custom 等）按 OpenAI 兼容端点 → ``ChatOpenAI``。
    """
    settings = get_settings()
    api_key = SecretStr(cfg.api_key)
    base_url = str(cfg.base_url) if cfg.base_url else None
    common: dict[str, Any] = {
        "timeout": settings.llm_http_read_timeout,
        "max_retries": settings.llm_max_retries,
    }
    if cfg.provider == "anthropic":
        # ChatAnthropic 的 max_tokens 字段带 alias，静态签名不含该 kwarg，故解包传入
        params: dict[str, Any] = {
            "model": cfg.model_name,
            "api_key": api_key,
            "base_url": base_url,
            "max_tokens": ANTHROPIC_MAX_TOKENS,
            **common,
        }
        return ChatAnthropic(**params)
    return ChatOpenAI(
        model=cfg.model_name,
        api_key=api_key,
        base_url=base_url,
        **common,
    )
