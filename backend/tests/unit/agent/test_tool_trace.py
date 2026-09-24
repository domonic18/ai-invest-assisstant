"""ToolTraceCallback 留痕单测：事件字段、时长、run_id 去重与陈项防御。"""

import uuid

import pytest
from structlog.testing import capture_logs

from app.agent.runtime.tool_trace import TOOL_TRACE, ToolTraceCallback

pytestmark = pytest.mark.unit


async def test_start_end_logs_event_fields_and_duration() -> None:
    callback = ToolTraceCallback()
    run_id = uuid.uuid4()
    with capture_logs() as logs:
        await callback.on_tool_start(
            {"name": "search_knowledge_base"},
            "",
            run_id=run_id,
            inputs={"q": "支撑位"},
        )
        await callback.on_tool_end("8 hits", run_id=run_id)
    assert [e["event"] for e in logs] == ["agent_tool_call", "agent_tool_call"]
    assert [e["phase"] for e in logs] == ["start", "end"]
    assert all(e["tool"] == "search_knowledge_base" for e in logs)
    assert logs[0]["args_summary"] == str({"q": "支撑位"})
    assert isinstance(logs[1]["duration_ms"], int)
    assert callback._starts == {}


async def test_missing_serialized_name_falls_back() -> None:
    callback = ToolTraceCallback()
    run_id = uuid.uuid4()
    with capture_logs() as logs:
        await callback.on_tool_start({}, "", run_id=run_id)
    assert logs[0]["tool"] == "unknown"


async def test_error_logs_phase_error_and_clears_state() -> None:
    callback = ToolTraceCallback()
    run_id = uuid.uuid4()
    with capture_logs() as logs:
        await callback.on_tool_start({"name": "get_stock_quote"}, "", run_id=run_id)
        await callback.on_tool_error(RuntimeError("boom"), run_id=run_id)
    assert logs[-1]["phase"] == "error"
    assert logs[-1]["error"] == "boom"
    assert "duration_ms" in logs[-1]
    assert callback._starts == {}


async def test_end_without_start_is_silent() -> None:
    callback = ToolTraceCallback()
    with capture_logs() as logs:
        await callback.on_tool_end("orphan", run_id=uuid.uuid4())
        await callback.on_tool_error(RuntimeError("orphan"), run_id=uuid.uuid4())
    assert logs == []


async def test_duplicate_start_ignored() -> None:
    callback = ToolTraceCallback()
    run_id = uuid.uuid4()
    with capture_logs() as logs:
        await callback.on_tool_start({"name": "t"}, "", run_id=run_id)
        await callback.on_tool_start({"name": "t"}, "", run_id=run_id)
    assert len([e for e in logs if e["phase"] == "start"]) == 1
    assert len(callback._starts) == 1


def test_singleton_is_shared_callback() -> None:
    assert isinstance(TOOL_TRACE, ToolTraceCallback)
    assert TOOL_TRACE is TOOL_TRACE
