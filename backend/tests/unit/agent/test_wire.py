"""Agent Protocol wire 序列化单测。"""

import asyncio
import typing

import pytest
from langchain_core.messages import AIMessageChunk, HumanMessage, ToolMessage
from langgraph.types import Interrupt

from app.agent.runtime.wire import (
    HEARTBEAT,
    RunRegistry,
    jsonable,
    merge_heartbeats,
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
class TestExtractEventMarker:
    def test_extracts_from_dict(self) -> None:
        from app.agent.runtime.wire import extract_event_marker

        marker = extract_event_marker(
            {"result": "ok", "__event__": {"type": "test.event"}}
        )
        assert marker == {"type": "test.event"}

    def test_extracts_from_json_string(self) -> None:
        from app.agent.runtime.wire import extract_event_marker

        marker = extract_event_marker('{"__event__": {"type": "test.event"}}')
        assert marker == {"type": "test.event"}

    def test_extracts_from_python_repr_string(self) -> None:
        from app.agent.runtime.wire import extract_event_marker

        marker = extract_event_marker("{'__event__': {'type': 'test.event'}}")
        assert marker == {"type": "test.event"}

    def test_returns_none_for_plain_string(self) -> None:
        from app.agent.runtime.wire import extract_event_marker

        assert extract_event_marker("plain result") is None


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

    @pytest.mark.asyncio
    async def test_has_active_run_scoped_by_thread(self) -> None:
        registry = RunRegistry()

        async def sleeper() -> None:
            await asyncio.sleep(30)

        task = asyncio.create_task(sleeper())
        registry.register("t1", "r1", task)
        assert registry.has_active_run("t1") is True
        assert registry.has_active_run("t2") is False

        registry.unregister("r1")
        assert registry.has_active_run("t1") is False
        task.cancel()


@pytest.mark.unit
class TestMergeHeartbeats:
    @staticmethod
    async def _source(items: list[str], delay: float) -> typing.AsyncIterator[str]:
        for item in items:
            await asyncio.sleep(delay)
            yield item

    @pytest.mark.asyncio
    async def test_idle_source_yields_heartbeats(self) -> None:
        # 源静默超过 interval 时插入心跳 tick；事件到达顺序保持
        out: list[object] = []
        async for item in merge_heartbeats(self._source(["a"], delay=0.25), 0.05):
            out.append(item)
        assert out[0] is HEARTBEAT
        assert out[-1] == "a"
        assert out.count(HEARTBEAT) >= 2

    @pytest.mark.asyncio
    async def test_busy_source_no_heartbeat(self) -> None:
        out = [item async for item in merge_heartbeats(self._source(["a", "b", "c"], delay=0.0), 0.1)]
        assert out == ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_source_exception_propagates(self) -> None:
        async def failing() -> typing.AsyncIterator[str]:
            yield "a"
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            async for _ in merge_heartbeats(failing(), 0.05):
                pass

    @pytest.mark.asyncio
    async def test_consumer_break_requires_explicit_aclose(self) -> None:
        # break 不关闭合并器（finally 不执行、pump 存活）；显式 aclose 后 pump 收口。
        # 与 runs.py 预算耗尽路径的用法一致
        pump_alive = asyncio.Event()

        async def source() -> typing.AsyncIterator[str]:
            pump_alive.set()
            try:
                while True:
                    await asyncio.sleep(10)
                    yield "never"
            finally:
                pump_alive.clear()

        merger = merge_heartbeats(source(), 0.05)
        async for _ in merger:
            break
        assert pump_alive.is_set()  # finally 尚未执行：调用方负责 aclose
        await merger.aclose()
        assert not pump_alive.is_set()
