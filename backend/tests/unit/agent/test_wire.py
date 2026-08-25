"""Agent Protocol wire 序列化单测。"""

import asyncio

import pytest
from langchain_core.messages import AIMessageChunk, HumanMessage, ToolMessage
from langgraph.types import Interrupt

from app.agent.runtime.wire import (
    RunRegistry,
    jsonable,
    namespace_label,
    serialize_message,
    sse_event,
)


@pytest.mark.unit
class TestSerializeMessage:
    def test_human_message(self) -> None:
        data = serialize_message(HumanMessage(content="你好", id="h1"))
        assert data == {"type": "human", "content": "你好", "id": "h1"}

    def test_ai_chunk_passes_through_anthropic_blocks(self) -> None:
        msg = AIMessageChunk(
            content=[{"type": "thinking", "thinking": "推理", "signature": "sig"}],
            id="a1",
        )
        data = serialize_message(msg)
        assert data["type"] == "AIMessageChunk"
        assert data["content"][0]["thinking"] == "推理"

    def test_ai_chunk_tool_call_chunks_normalized(self) -> None:
        msg = AIMessageChunk(
            content="",
            id="a2",
            tool_call_chunks=[
                {"name": "get_stock_kline", "args": '{"stock', "id": "call1", "index": 1}
            ],
        )
        data = serialize_message(msg)
        assert data["tool_call_chunks"] == [
            {"index": 1, "id": "call1", "name": "get_stock_kline", "args": '{"stock'}
        ]

    def test_tool_message_fields(self) -> None:
        msg = ToolMessage(
            content="[]", tool_call_id="call1", name="get_stock_kline", id="t1"
        )
        data = serialize_message(msg)
        assert data["type"] == "tool"
        assert data["tool_call_id"] == "call1"
        assert data["status"] == "success"


@pytest.mark.unit
class TestJsonable:
    def test_interrupt_payload(self) -> None:
        payload = jsonable(
            {"__interrupt__": [Interrupt(value="请确认操作")]}
        )
        interrupt = payload["__interrupt__"][0]
        assert interrupt["value"] == "请确认操作"
        assert interrupt["id"]

    def test_nested_messages_and_dates(self) -> None:
        from datetime import date

        payload = jsonable(
            {"messages": [HumanMessage(content="hi", id="h1")], "day": date(2026, 8, 25)}
        )
        assert payload["messages"][0]["type"] == "human"
        assert payload["day"] == "2026-08-25"


@pytest.mark.unit
class TestSseEvent:
    def test_frame_format(self) -> None:
        frame = sse_event("messages", [{"type": "ai"}])
        assert frame.startswith("event: messages\ndata: ")
        assert frame.endswith("\n\n")


@pytest.mark.unit
class TestNamespaceLabel:
    def test_empty_namespaces_is_root(self) -> None:
        assert namespace_label(()) == ""

    def test_subgraph_label_takes_last_segment(self) -> None:
        assert namespace_label(("task:abc123",)) == "task:abc123"
        assert namespace_label(("n1:1", "task:xyz:sub")) == "task:xyz:sub"


@pytest.mark.unit
class TestRunRegistry:
    @pytest.mark.asyncio
    async def test_cancel_matches_thread_and_run(self) -> None:
        registry = RunRegistry()

        async def sleeper() -> None:
            await asyncio.sleep(30)

        task = asyncio.create_task(sleeper())
        registry.register("t1", "r1", task)

        assert registry.cancel("t2", "r1") is False  # 线程不匹配
        assert registry.cancel("t1", "r1") is True
        with pytest.raises(asyncio.CancelledError):
            await task

        registry.unregister("r1")
        assert registry.cancel("t1", "r1") is False
