"""交易 Agent 运行时人设/方法论注入测试（D28 身份段 + D30 方法论静态层）。"""

from unittest.mock import AsyncMock, patch

import pytest

from app.agent.runtime.trading_agent import (
    _fingerprint,
    _methodology_section,
    _persona_section,
)
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

    def test_skips_empty_tagline_and_style(self) -> None:
        """D30：新建精简（仅名称），空值行不输出、不出现空括号。"""
        section = _persona_section("新 Agent", "", "", "")
        assert "新 Agent" in section
        assert "（）" not in section
        assert "策略风格" not in section


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

    def test_sensitive_to_methodology_binding(self) -> None:
        """D30：方法论绑定/换绑失效缓存重建。"""
        assert _fingerprint("short-line", "p1", _PERSONA, _cfg()) != _fingerprint(
            "short-line", "p1", _PERSONA, _cfg(), methodology_source_id=1
        )
        assert _fingerprint(
            "short-line", "p1", _PERSONA, _cfg(), methodology_source_id=1
        ) != _fingerprint("short-line", "p1", _PERSONA, _cfg(), methodology_source_id=2)


@pytest.mark.unit
class TestMethodologySection:
    """D30：会话注入方法论基座静态层（总纲 + 纪律，跳过检索层）。"""

    @pytest.mark.asyncio
    async def test_empty_when_not_bound(self) -> None:
        session = AsyncMock()
        source_id, text = await _methodology_section(session, None)
        assert source_id is None
        assert text == ""

    @pytest.mark.asyncio
    async def test_includes_outline_and_disciplines_without_query(self) -> None:
        session = AsyncMock()
        data = {
            "source_id": 1,
            "outline": "- 第一章 体系",
            "disciplines": [{"id": 1, "title": "不追高", "body": "偏离 3% 不追"}],
            "relevant": [],
        }
        with patch(
            "app.services.trading.agent_methodology.build_methodology_input",
            AsyncMock(return_value=data),
        ) as build_mock:
            source_id, text = await _methodology_section(session, 1)

        assert source_id == 1
        assert "## 方法论基座" in text
        assert "- 第一章 体系" in text
        assert "- 不追高：偏离 3% 不追" in text
        # query_text=None 跳过当日盘面检索层
        assert build_mock.await_args.kwargs["query_text"] is None

    @pytest.mark.asyncio
    async def test_unavailable_source_renders_empty(self) -> None:
        session = AsyncMock()
        with patch(
            "app.services.trading.agent_methodology.build_methodology_input",
            AsyncMock(return_value=None),
        ):
            source_id, text = await _methodology_section(session, 1)
        assert source_id is None
        assert text == ""
