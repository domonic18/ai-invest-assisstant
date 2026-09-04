"""个股每日分析 deepagents skill 执行器测试（JSON 解析/重试/校验）。"""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.core.prompt_loader import PromptConfig, PromptSection
from app.agent.skills.stock_daily_analysis_agent import (
    SkillOutputError,
    _parse_sections,
    run_skill,
)

_TRADE_DATE = date(2026, 9, 1)

_SECTIONS = [
    PromptSection(key="intraday_review", title="盘面解读", requirements="解读盘面"),
    PromptSection(key="strategy", title="操作策略", requirements="给出策略"),
]

_PROMPT_CONFIG = PromptConfig(
    id="stock-daily-analysis",
    name="个股每日 AI 分析",
    version="2.0.0",
    system_prompt="你是分析师。最终回复只能是一个 JSON 对象。",
    user_prompt_template=(
        "请生成 {stock_name}（{stock_code}）{trade_date} 的每日个股分析：\n"
        "{section_instructions}"
    ),
    sections=_SECTIONS,
)

_VALID_JSON = '{"sections": {"intraday_review": "盘面内容", "strategy": "策略内容"}}'


class _FakeAgent:
    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.prompts: list[str] = []

    async def ainvoke(self, payload: dict) -> dict:
        self.prompts.append(payload["messages"][0].content)
        return {"messages": [SimpleNamespace(content=self.replies.pop(0))]}


def _patch_run_env(agent: _FakeAgent):
    cfg = SimpleNamespace(
        provider="openai", model_name="gpt-4o", api_key="k", base_url=None
    )
    return (
        patch(
            "app.agent.skills.stock_daily_analysis_agent.resolve_default_llm",
            AsyncMock(return_value=cfg),
        ),
        patch(
            "app.agent.skills.stock_daily_analysis_agent.build_langchain_model",
            lambda _cfg: object(),
        ),
        patch("deepagents.create_deep_agent", return_value=agent),
    )


@pytest.mark.unit
class TestParseSections:
    def test_parses_valid_json(self) -> None:
        contents = _parse_sections(_VALID_JSON, _SECTIONS)
        assert contents == {"intraday_review": "盘面内容", "strategy": "策略内容"}

    def test_parses_json_wrapped_in_text(self) -> None:
        text = f"分析结论如下：\n```json\n{_VALID_JSON}\n```"
        assert _parse_sections(text, _SECTIONS)["strategy"] == "策略内容"

    def test_raises_when_no_json(self) -> None:
        with pytest.raises(SkillOutputError):
            _parse_sections("没有 JSON 的回复", _SECTIONS)

    def test_raises_when_sections_missing(self) -> None:
        with pytest.raises(SkillOutputError):
            _parse_sections('{"foo": 1}', _SECTIONS)

    def test_raises_when_section_key_missing(self) -> None:
        text = '{"sections": {"intraday_review": "内容"}}'
        with pytest.raises(SkillOutputError, match="strategy"):
            _parse_sections(text, _SECTIONS)


@pytest.mark.unit
class TestRunSkill:
    @pytest.mark.asyncio
    async def test_returns_sections_model_and_latency(self) -> None:
        agent = _FakeAgent([_VALID_JSON])
        patches = _patch_run_env(agent)
        with patches[0], patches[1], patches[2]:
            contents, model, latency = await run_skill(
                AsyncMock(),
                "600519",
                trade_date=_TRADE_DATE,
                stock_name="贵州茅台",
                prompt_config=_PROMPT_CONFIG,
            )

        assert contents["intraday_review"] == "盘面内容"
        assert model == "openai/gpt-4o"
        assert latency >= 0
        assert len(agent.prompts) == 1
        assert "贵州茅台" in agent.prompts[0]
        assert "intraday_review" in agent.prompts[0]

    @pytest.mark.asyncio
    async def test_retries_once_on_invalid_output(self) -> None:
        agent = _FakeAgent(["这不是 JSON", _VALID_JSON])
        patches = _patch_run_env(agent)
        with patches[0], patches[1], patches[2]:
            contents, _, _ = await run_skill(
                AsyncMock(),
                "600519",
                trade_date=_TRADE_DATE,
                stock_name="贵州茅台",
                prompt_config=_PROMPT_CONFIG,
            )

        assert contents["strategy"] == "策略内容"
        assert len(agent.prompts) == 2
        assert "重试" in agent.prompts[1]

    @pytest.mark.asyncio
    async def test_raises_after_retry_exhausted(self) -> None:
        agent = _FakeAgent(["坏输出", "还是坏输出"])
        patches = _patch_run_env(agent)
        with patches[0], patches[1], patches[2], pytest.raises(SkillOutputError):
            await run_skill(
                AsyncMock(),
                "600519",
                trade_date=_TRADE_DATE,
                stock_name="贵州茅台",
                prompt_config=_PROMPT_CONFIG,
            )

        assert len(agent.prompts) == 2
