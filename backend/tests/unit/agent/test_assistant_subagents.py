"""领域子代理声明单测。"""

import pytest

from app.agent.runtime.assistant_subagents import build_subagents

EXPECTED = {
    "market-analyst": {
        "get_stock_quote",
        "get_stock_kline",
        "get_market_overview",
        "get_auction_summary",
    },
    "fundamental-analyst": {"query_financial_data", "search_vector_kb"},
    "news-scout": {"search_news", "search_vector_kb", "get_sector_fund_flow"},
}


@pytest.mark.unit
class TestBuildSubagents:
    def test_three_domain_subagents_declared(self) -> None:
        subagents = build_subagents()
        assert {s["name"] for s in subagents} == set(EXPECTED)

    def test_tool_subsets_match_plan(self) -> None:
        subagents = {s["name"]: s for s in build_subagents()}
        for name, expected_tools in EXPECTED.items():
            tool_names = {t.name for t in subagents[name]["tools"]}
            assert tool_names == expected_tools, name

    def test_prompts_loaded_from_yaml(self) -> None:
        for subagent in build_subagents():
            prompt = subagent["system_prompt"]
            assert len(prompt) >= 50, subagent["name"]
            assert "子代理" in prompt, subagent["name"]

    def test_descriptions_are_delegation_friendly(self) -> None:
        for subagent in build_subagents():
            assert len(subagent["description"]) >= 20, subagent["name"]
