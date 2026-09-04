"""LLM 模型路由与 Agent 构建辅助函数。"""

import httpx
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel, AnthropicModelSettings
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.openai import OpenAIProvider

from app.agent.core.prompt_loader import PromptConfig
from app.core.config import get_settings


def parse_model_string(model_string: str | None) -> tuple[str, str]:
    """解析 'provider/model' 格式的模型字符串。"""
    if not model_string:
        return "openai", "gpt-4o"
    if "/" in model_string:
        provider, model = model_string.split("/", 1)
        return provider, model
    return "openai", model_string


def _build_http_client() -> httpx.AsyncClient:
    """创建带有统一超时的 httpx 异步客户端供 LLM provider 使用。"""
    settings = get_settings()
    timeout = httpx.Timeout(
        settings.llm_http_read_timeout,
        connect=settings.llm_http_connect_timeout,
        write=settings.llm_http_write_timeout,
        pool=settings.llm_http_pool_timeout,
    )
    return httpx.AsyncClient(timeout=timeout)


def build_model(
    provider: str,
    model: str,
    api_key: str,
    base_url: str | None = None,
) -> OpenAIChatModel | AnthropicModel:
    settings = get_settings()
    http_client = _build_http_client()
    if provider == "anthropic":
        anthropic_client = AsyncAnthropic(
            api_key=api_key,
            base_url=base_url,
            http_client=http_client,
            max_retries=settings.llm_max_retries,
        )
        return AnthropicModel(
            model,
            provider=AnthropicProvider(anthropic_client=anthropic_client),
        )
    # deepseek / zhipu / custom 等均提供 OpenAI 兼容接口
    openai_client = AsyncOpenAI(
        base_url=base_url,
        api_key=api_key,
        http_client=http_client,
        max_retries=settings.llm_max_retries,
    )
    return OpenAIChatModel(
        model,
        provider=OpenAIProvider(openai_client=openai_client),
    )


def build_agent(
    prompt_config: PromptConfig,
    model_config: dict,
    result_type: type | None = None,
) -> Agent:
    provider, model = parse_model_string(prompt_config.model)
    # 显式指定 provider 时以 model 配置为准
    provider = model_config.get("provider", provider)
    model = model_config.get("model", model)
    model_instance = build_model(
        provider=provider,
        model=model,
        api_key=model_config["api_key"],
        base_url=model_config.get("base_url"),
    )
    model_settings = None
    if provider == "anthropic" and result_type is not None:
        # 结构化输出使用强制 tool_choice，与 thinking 不兼容（Anthropic 与
        # Kimi 等 Anthropic 协议端点均会拒绝），因此显式关闭 thinking
        model_settings = AnthropicModelSettings(anthropic_thinking={"type": "disabled"})
    return Agent(
        model_instance,
        system_prompt=prompt_config.system_prompt,
        output_type=result_type,  # type: ignore[arg-type]
        model_settings=model_settings,
        defer_model_check=True,
    )
