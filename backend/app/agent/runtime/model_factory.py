"""llm_config → LangChain 聊天模型实例工厂。

对话助手（deepagents）运行时使用；既有 PydanticAI 单轮管线继续走
``app.agent.core.llm_router.build_model``，两者互不影响。
"""

from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.services.llm_config_service import ResolvedLLMConfig

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
    api_key = SecretStr(cfg.api_key)
    base_url = str(cfg.base_url) if cfg.base_url else None
    if cfg.provider == "anthropic":
        # ChatAnthropic 的 max_tokens 字段带 alias，静态签名不含该 kwarg，故解包传入
        params: dict[str, Any] = {
            "model": cfg.model_name,
            "api_key": api_key,
            "base_url": base_url,
            "max_tokens": ANTHROPIC_MAX_TOKENS,
        }
        return ChatAnthropic(**params)
    return ChatOpenAI(
        model=cfg.model_name,
        api_key=api_key,
        base_url=base_url,
    )
