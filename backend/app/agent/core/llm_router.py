from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.openai import OpenAIProvider

from app.agent.core.prompt_loader import PromptConfig


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


def build_agent(prompt_config: PromptConfig, model_config: dict) -> Agent:
    model = build_model(
        provider=model_config["provider"],
        model=prompt_config.model or model_config["model"],
        api_key=model_config["api_key"],
        base_url=model_config.get("base_url"),
    )
    return Agent(
        model,
        system_prompt=prompt_config.system_prompt,
        defer_model_check=True,
    )
