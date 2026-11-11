"""assistant runtime 模型工厂单测。"""

import httpx
import pytest

from app.agent.runtime.model_factory import ANTHROPIC_MAX_TOKENS, build_langchain_model
from app.core.config import get_settings
from app.services.admin.llm_config_service import ResolvedLLMConfig


def _cfg(provider: str) -> ResolvedLLMConfig:
    return ResolvedLLMConfig(
        config_id=1,
        provider=provider,
        protocol="anthropic" if provider == "anthropic" else "openai",
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

    def test_openai_timeout_splits_connect_and_read(self) -> None:
        """OpenAI 兼容端点 connect/read 超时分离：建连黑洞不拖满读超时。"""
        from langchain_openai import ChatOpenAI

        model = build_langchain_model(_cfg("openai"))
        assert isinstance(model, ChatOpenAI)
        timeout = model.request_timeout
        assert isinstance(timeout, httpx.Timeout)
        assert timeout.connect == get_settings().llm_http_connect_timeout
        assert timeout.read == get_settings().llm_http_read_timeout

    def test_anthropic_timeout_is_read_float(self) -> None:
        """ChatAnthropic 的 timeout 字段仅收 float，保持读超时兜底语义。"""
        model = build_langchain_model(_cfg("anthropic"))
        assert model.default_request_timeout == get_settings().llm_http_read_timeout

    def test_read_timeout_override_applies_to_both_protocols(self) -> None:
        """出口专属读超时覆盖全局值（助手出口兜「慢但成功」盲区），connect 不受影响。"""
        from langchain_anthropic import ChatAnthropic
        from langchain_openai import ChatOpenAI

        openai_model = build_langchain_model(_cfg("openai"), read_timeout=240.0)
        assert isinstance(openai_model, ChatOpenAI)
        assert isinstance(openai_model.request_timeout, httpx.Timeout)
        assert openai_model.request_timeout.read == 240.0
        assert (
            openai_model.request_timeout.connect == get_settings().llm_http_connect_timeout
        )

        anthropic_model = build_langchain_model(_cfg("anthropic"), read_timeout=240.0)
        assert isinstance(anthropic_model, ChatAnthropic)
        assert anthropic_model.default_request_timeout == 240.0

    def test_anthropic_default_budget_leaves_thinking_headroom(self) -> None:
        """默认预算必须给足：thinking 与输出共享，8192 会被长思考精确烧满
        致最终回复截断（kimi k3.1-pro 复盘事故），回归时在此显式失败。"""
        assert ANTHROPIC_MAX_TOKENS >= 32768
        model = build_langchain_model(_cfg("anthropic"))
        assert model.max_tokens == ANTHROPIC_MAX_TOKENS
