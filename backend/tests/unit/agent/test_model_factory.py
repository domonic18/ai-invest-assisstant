"""assistant runtime 模型工厂单测。"""

import pytest

from app.agent.runtime.model_factory import build_langchain_model
from app.services.llm_config_service import ResolvedLLMConfig


def _cfg(provider: str) -> ResolvedLLMConfig:
    return ResolvedLLMConfig(
        config_id=1,
        provider=provider,
        base_url="https://example.com/api/",
        api_key="test-key",
        model_name="test-model",
        extra={},
    )


@pytest.mark.unit
class TestBuildLangChainModel:
    def test_anthropic_provider_builds_chat_anthropic(self) -> None:
        from langchain_anthropic import ChatAnthropic

        model = build_langchain_model(_cfg("anthropic"))
        assert isinstance(model, ChatAnthropic)

    def test_openai_provider_builds_chat_openai(self) -> None:
        from langchain_openai import ChatOpenAI

        model = build_langchain_model(_cfg("openai"))
        assert isinstance(model, ChatOpenAI)

    def test_custom_provider_falls_back_to_openai_compatible(self) -> None:
        from langchain_openai import ChatOpenAI

        model = build_langchain_model(_cfg("custom"))
        assert isinstance(model, ChatOpenAI)
