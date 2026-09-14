"""ask_user 问题卡工具单测（arch/09 §7.3）：参数校验、标记形状与 wire 提取。"""

import pytest

from app.agent.runtime import wire
from app.agent.tools.interaction_tools import ask_user, build_question_marker

OPTIONS = [
    {"value": "append", "label": "保留并新增"},
    {"value": "replace", "label": "覆盖 AI 画线"},
    {"value": "cancel", "label": "取消"},
]


@pytest.mark.unit
class TestAskUser:
    @pytest.mark.asyncio
    async def test_valid_call_returns_question_marker(self) -> None:
        result = await ask_user.ainvoke(
            {"question": "检测到已有画线，如何处理？", "options": OPTIONS, "default": "append"}
        )
        marker = result["__question__"]
        assert marker["type"] == "question"
        assert marker["question"] == "检测到已有画线，如何处理？"
        assert [o["label"] for o in marker["options"]] == ["保留并新增", "覆盖 AI 画线", "取消"]
        assert marker["default"] == "append"

    @pytest.mark.asyncio
    async def test_rejects_fewer_than_two_options(self) -> None:
        result = await ask_user.ainvoke(
            {"question": "继续？", "options": [{"value": "yes", "label": "是"}]}
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_rejects_duplicate_or_empty_values(self) -> None:
        result = await ask_user.ainvoke(
            {"question": "选？", "options": [{"value": "a", "label": "甲"}, {"value": "a", "label": "乙"}]}
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_rejects_default_not_in_options(self) -> None:
        result = await ask_user.ainvoke(
            {"question": "选？", "options": OPTIONS, "default": "nope"}
        )
        assert "error" in result


@pytest.mark.unit
class TestExtractQuestionMarker:
    def test_extracts_from_dict(self) -> None:
        marker = build_question_marker("问题", OPTIONS[:2], None)
        content = {"__question__": marker}
        extracted = wire.extract_question_marker(content)
        assert extracted is not None and extracted["question"] == "问题"

    def test_extracts_from_json_string(self) -> None:
        import json

        content = json.dumps({"__question__": build_question_marker("q", OPTIONS[:2], "a")})
        assert wire.extract_question_marker(content) is not None

    def test_returns_none_for_plain_content(self) -> None:
        assert wire.extract_question_marker({"error": "x"}) is None
        assert wire.extract_question_marker("普通工具结果") is None

    def test_event_marker_still_works_alongside(self) -> None:
        content = {"__event__": {"type": "kline_drawing.complete"}}
        assert wire.extract_event_marker(content) is not None
        assert wire.extract_question_marker(content) is None
