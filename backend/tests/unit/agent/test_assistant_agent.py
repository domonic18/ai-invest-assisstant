"""assistant_agent 运行时组装单测（不触网、不连库）。"""

from unittest.mock import AsyncMock, patch

import pytest
from langgraph.graph.state import CompiledStateGraph

from app.services.admin.llm_config_service import ResolvedLLMConfig


def _resolved() -> ResolvedLLMConfig:
    return ResolvedLLMConfig(
        config_id=1,
        provider="openai",
        base_url="https://example.com/api/",
        api_key="test-key",
        model_name="test-model",
        extra={},
    )


@pytest.fixture(autouse=True)
def _reset_cache():
    from app.agent.runtime import assistant_agent

    assistant_agent.reset_assistant_agent()
    yield
    assistant_agent.reset_assistant_agent()


@pytest.mark.unit
class TestAssistantAgent:
    def test_system_prompt_loads_from_yaml(self) -> None:
        from app.agent.runtime.assistant_agent import load_assistant_system_prompt

        prompt = load_assistant_system_prompt()
        assert "对话助手" in prompt
        assert "工具" in prompt

    @pytest.mark.asyncio
    async def test_get_assistant_agent_builds_and_caches(self) -> None:
        from langgraph.checkpoint.memory import MemorySaver

        from app.agent.runtime import assistant_agent

        checkpointer = MemorySaver()
        with (
            patch(
                "app.agent.runtime.assistant_agent.resolve_default_llm",
                AsyncMock(return_value=_resolved()),
            ),
            patch(
                "app.agent.runtime.assistant_agent.get_checkpointer",
                AsyncMock(return_value=checkpointer),
            ) as get_cp,
        ):
            agent1 = await assistant_agent.get_assistant_agent()
            agent2 = await assistant_agent.get_assistant_agent()

        assert isinstance(agent1, CompiledStateGraph)
        assert agent2 is agent1
        assert get_cp.await_count == 1

    @pytest.mark.asyncio
    async def test_agent_includes_todo_list_middleware(self) -> None:
        from langgraph.checkpoint.memory import MemorySaver

        from app.agent.runtime import assistant_agent

        with (
            patch(
                "app.agent.runtime.assistant_agent.resolve_default_llm",
                AsyncMock(return_value=_resolved()),
            ),
            patch(
                "app.agent.runtime.assistant_agent.get_checkpointer",
                AsyncMock(return_value=MemorySaver()),
            ),
        ):
            agent = await assistant_agent.get_assistant_agent()

        graph = agent.get_graph()
        node_names = set(graph.nodes.keys())
        assert "TodoListMiddleware.after_model" in node_names
        assert "todos" in agent.channels

    @pytest.mark.asyncio
    async def test_agent_includes_skills_channels(self) -> None:
        from langgraph.checkpoint.memory import MemorySaver

        from app.agent.runtime import assistant_agent

        with (
            patch(
                "app.agent.runtime.assistant_agent.resolve_default_llm",
                AsyncMock(return_value=_resolved()),
            ),
            patch(
                "app.agent.runtime.assistant_agent.get_checkpointer",
                AsyncMock(return_value=MemorySaver()),
            ),
        ):
            agent = await assistant_agent.get_assistant_agent()

        assert "skills_metadata" in agent.channels
        assert "skills_load_errors" in agent.channels
