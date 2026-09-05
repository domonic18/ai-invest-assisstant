"""涨停归因 deepagents skill 执行器测试（结构化 JSON 解析/重试）。"""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.core.prompt_loader import PromptConfig
from app.agent.skills.limit_up_review_agent import run_skill
from app.agent.skills.skill_runtime import SkillOutputError

_TRADE_DATE = date(2026, 9, 4)

_PROMPT_CONFIG = PromptConfig(
    id="limit-up-review",
    name="涨停复盘 AI 归因",
    version="1.1.0",
    system_prompt="你是涨停归因分析师。最终回复只能是一个 JSON 对象。",
    user_prompt_template=(
        '请对 {trade_date} 的涨停板进行题材归因分析（涨停池共 {pool_count} 只）。'
    ),
)

_VALID_JSON = (
    '{"groups": [{"theme": "算力", "reason": "政策催化", '
    '"stock_codes": ["000001", "600519"]}], '
    '"stock_themes": {"000001": ["算力"], "600519": ["算力", "CPO"]}}'
)


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
            "app.agent.skills.limit_up_review_agent.resolve_default_llm",
            AsyncMock(return_value=cfg),
        ),
        patch(
            "app.agent.skills.limit_up_review_agent.build_langchain_model",
            lambda _cfg: object(),
        ),
        patch("deepagents.create_deep_agent", return_value=agent),
    )


@pytest.mark.unit
class TestRunSkill:
    @pytest.mark.asyncio
    async def test_returns_parsed_content_model_and_latency(self) -> None:
        agent = _FakeAgent([_VALID_JSON])
        patches = _patch_run_env(agent)
        with patches[0], patches[1], patches[2]:
            content, model, latency = await run_skill(
                AsyncMock(),
                trade_date=_TRADE_DATE,
                pool_count=2,
                prompt_config=_PROMPT_CONFIG,
            )

        assert content.groups[0].theme == "算力"
        assert content.groups[0].stock_codes == ["000001", "600519"]
        assert content.stock_themes["600519"] == ["算力", "CPO"]
        assert model == "openai/gpt-4o"
        assert latency >= 0
        assert len(agent.prompts) == 1
        assert _TRADE_DATE.isoformat() in agent.prompts[0]
        assert "2" in agent.prompts[0]

    @pytest.mark.asyncio
    async def test_retries_once_on_schema_violation(self) -> None:
        agent = _FakeAgent(['{"groups": "不是列表"}', _VALID_JSON])
        patches = _patch_run_env(agent)
        with patches[0], patches[1], patches[2]:
            content, _, _ = await run_skill(
                AsyncMock(),
                trade_date=_TRADE_DATE,
                pool_count=2,
                prompt_config=_PROMPT_CONFIG,
            )

        assert content.groups[0].theme == "算力"
        assert len(agent.prompts) == 2
        assert "重试" in agent.prompts[1]

    @pytest.mark.asyncio
    async def test_raises_after_retry_exhausted(self) -> None:
        agent = _FakeAgent(["坏输出", '{"bad": true}'])
        patches = _patch_run_env(agent)
        with (
            patches[0],
            patches[1],
            patches[2],
            pytest.raises(SkillOutputError, match="schema"),
        ):
            await run_skill(
                AsyncMock(),
                trade_date=_TRADE_DATE,
                pool_count=2,
                prompt_config=_PROMPT_CONFIG,
            )

        assert len(agent.prompts) == 2
