"""大盘每日复盘 deepagents skill 执行器测试（JSON 解析/重试/校验）。"""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.core.prompt_loader import PromptConfig, PromptSection
from app.agent.skills.market_review_agent import run_skill
from app.agent.skills.skill_runtime import SkillOutputError

_TRADE_DATE = date(2026, 9, 4)

_SECTIONS = [
    PromptSection(key="overview", title="AI 大盘综述", requirements="撰写综述"),
    PromptSection(key="risk_advice", title="风险提示与策略建议", requirements="提示风险"),
]

_PROMPT_CONFIG = PromptConfig(
    id="market-daily-review",
    name="大盘每日复盘综述",
    version="2.0.0",
    system_prompt="你是复盘分析师。最终回复只能是一个 JSON 对象。",
    user_prompt_template="请生成 {trade_date} 的每日大盘复盘综述：\n{section_instructions}",
    sections=_SECTIONS,
)

_VALID_JSON = '{"sections": {"overview": "综述内容", "risk_advice": "风险内容"}}'


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
            "app.agent.skills.market_review_agent.resolve_default_llm",
            AsyncMock(return_value=cfg),
        ),
        patch(
            "app.agent.skills.market_review_agent.build_langchain_model",
            lambda _cfg: object(),
        ),
        patch("deepagents.create_deep_agent", return_value=agent),
    )


@pytest.mark.unit
class TestRunSkill:
    @pytest.mark.asyncio
    async def test_returns_sections_model_and_latency(self) -> None:
        agent = _FakeAgent([_VALID_JSON])
        patches = _patch_run_env(agent)
        with patches[0], patches[1], patches[2]:
            contents, model, latency = await run_skill(
                AsyncMock(), trade_date=_TRADE_DATE, prompt_config=_PROMPT_CONFIG
            )

        assert contents["overview"] == "综述内容"
        assert contents["risk_advice"] == "风险内容"
        assert model == "openai/gpt-4o"
        assert latency >= 0
        assert len(agent.prompts) == 1
        assert _TRADE_DATE.isoformat() in agent.prompts[0]
        assert "overview" in agent.prompts[0]

    @pytest.mark.asyncio
    async def test_retries_once_on_invalid_output(self) -> None:
        agent = _FakeAgent(["这不是 JSON", _VALID_JSON])
        patches = _patch_run_env(agent)
        with patches[0], patches[1], patches[2]:
            contents, _, _ = await run_skill(
                AsyncMock(), trade_date=_TRADE_DATE, prompt_config=_PROMPT_CONFIG
            )

        assert contents["risk_advice"] == "风险内容"
        assert len(agent.prompts) == 2
        assert "重试" in agent.prompts[1]

    @pytest.mark.asyncio
    async def test_raises_after_retry_exhausted(self) -> None:
        agent = _FakeAgent(["坏输出", "还是坏输出"])
        patches = _patch_run_env(agent)
        with patches[0], patches[1], patches[2], pytest.raises(SkillOutputError):
            await run_skill(
                AsyncMock(), trade_date=_TRADE_DATE, prompt_config=_PROMPT_CONFIG
            )

        assert len(agent.prompts) == 2
