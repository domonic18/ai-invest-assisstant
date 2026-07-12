"""LLM model routing and Agent building helpers."""

from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.openai import OpenAIProvider

from app.agent.core.prompt_loader import PromptConfig


def parse_model_string(model_string: str | None) -> tuple[str, str]:
    """解析 'provider/model' 格式的模型字符串。"""
    if not model_string:
        return "openai", "gpt-4o"
    if "/" in model_string:
        provider, model = model_string.split("/", 1)
        return provider, model
    return "openai", model_string


def build_model(
    provider: str,
    model: str,
    api_key: str,
    base_url: str | None = None,
) -> OpenAIChatModel | AnthropicModel:
    if provider == "openai":
        return OpenAIChatModel(
            model,
            provider=OpenAIProvider(base_url=base_url, api_key=api_key),
        )
    if provider == "anthropic":
        return AnthropicModel(
            model,
            provider=AnthropicProvider(api_key=api_key, base_url=base_url),
        )
    raise ValueError(f"Unsupported provider: {provider}")


def build_agent(
    prompt_config: PromptConfig,
    model_config: dict,
    result_type: type | None = None,
) -> Agent:
    provider, model = parse_model_string(prompt_config.model)
    # Model config overrides if explicit provider is given
    provider = model_config.get("provider", provider)
    model = model_config.get("model", model)
    model_instance = build_model(
        provider=provider,
        model=model,
        api_key=model_config["api_key"],
        base_url=model_config.get("base_url"),
    )
    return Agent(
        model_instance,
        system_prompt=prompt_config.system_prompt,
        output_type=result_type,  # type: ignore[arg-type]
        defer_model_check=True,
    )
