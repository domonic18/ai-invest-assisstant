"""交易 Agent 运行时人设注入测试（D28：身份段拼装 + 缓存指纹敏感性）。"""

import pytest

from app.agent.runtime.trading_agent import _fingerprint, _persona_section
from app.services.admin.llm_config_service import ResolvedLLMConfig

_PERSONA = ("短线猎手", "趋势短线：顺势而为", "进取", "主线板块选股，回踩接回")


def _cfg(**overrides: object) -> ResolvedLLMConfig:
    base: dict[str, object] = {
        "config_id": 1,
        "provider": "kimi",
        "protocol": "anthropic",
        "base_url": "https://api.kimi.com",
        "api_key": "sk-test",
        "model_name": "kimi-latest",
        "extra": {},
    }
    base.update(overrides)
    return ResolvedLLMConfig(**base)  # type: ignore[arg-type]


@pytest.mark.unit
class TestPersonaSection:
    def test_contains_registry_fields(self) -> None:
        section = _persona_section(*_PERSONA)
        assert "短线猎手" in section
        assert "趋势短线：顺势而为" in section
        assert "进取" in section
        assert "主线板块选股" in section
        assert section.startswith("## 你的身份")


@pytest.mark.unit
class TestFingerprint:
    def test_stable_for_same_inputs(self) -> None:
        assert _fingerprint("short-line", "p1", _PERSONA, _cfg()) == _fingerprint(
            "short-line", "p1", _PERSONA, _cfg()
        )

    def test_sensitive_to_persona_edit(self) -> None:
        """注册表人设编辑（如改标语）必须失效缓存重建（D28 全链路生效）。"""
        edited = ("短线猎手", "改后的标语", "进取", "主线板块选股，回踩接回")
        assert _fingerprint("short-line", "p1", _PERSONA, _cfg()) != _fingerprint(
            "short-line", "p1", edited, _cfg()
        )

    def test_sensitive_to_prompt_and_config(self) -> None:
        assert _fingerprint("short-line", "p1", _PERSONA, _cfg()) != _fingerprint(
            "short-line", "p2", _PERSONA, _cfg()
        )
        assert _fingerprint("short-line", "p1", _PERSONA, _cfg()) != _fingerprint(
            "short-line", "p1", _PERSONA, _cfg(model_name="other")
        )
