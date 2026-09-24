"""知识库消费工具（批次 H1）单测：全员注册钉死 + 压缩卡片/引用定位/media 引用。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.tools import build_assistant_tools
from app.agent.tools import kb_tools as kt
from app.schemas.kb import (
    KbSearchPointHit,
    KbSearchResponse,
    KbSearchSegmentHit,
)


class _ExecResult:
    """SQLAlchemy execute 结果桩：first / all / scalars().all() 三形态。"""

    def __init__(
        self,
        *,
        first: object = None,
        rows: list | None = None,
        scalars_all: list | None = None,
    ) -> None:
        self._first = first
        self._rows = rows
        self._scalars_all = scalars_all

    def first(self) -> object:
        return self._first

    def all(self) -> list:
        return self._rows or []

    def scalars(self) -> SimpleNamespace:
        return SimpleNamespace(all=lambda: self._scalars_all or [])


class _SessionCtx:
    def __init__(self, results: list[_ExecResult]) -> None:
        session = SimpleNamespace(execute=AsyncMock(side_effect=results))
        self._session = session

    async def __aenter__(self) -> SimpleNamespace:
        return self._session

    async def __aexit__(self, *exc: object) -> None:
        return None


def _course_hit() -> KbSearchPointHit:
    return KbSearchPointHit(
        id=11,
        source_id=1,
        media_id=2,
        media_kind="video",
        episode_no=3,
        media_title="第3课 均线系统",
        point_type="method",
        title="均线金叉加仓纪律",
        body="金叉出现后不追高，等待回踩五日线确认再分批加仓。" * 25,
        term_definition="金叉：短期均线上穿长期均线。",
        excerpt="你看这个金叉，不能激动地直接打满仓。",
        chapter_path=["第二章", "均线系统"],
        start_ms=330_000,
        end_ms=370_000,
        score=0.03,
    )


def _book_hit() -> KbSearchPointHit:
    return KbSearchPointHit(
        id=12,
        source_id=2,
        media_id=5,
        media_kind="book",
        episode_no=None,
        media_title="缠中说禅",
        point_type="theorem",
        title="中枢递归定义",
        body="中枢由至少三段次级别走势类型重叠区间构成。",
        excerpt="",
        chapter_path=["第一册"],
        page_start=45,
        page_end=47,
        score=0.02,
    )


@pytest.mark.unit
class TestKbToolRegistration:
    def test_registry_includes_kb_tool_by_default(self) -> None:
        """知识库检索工具默认注入（播放权限由 playback-token 白名单控制）。"""
        names = [t.name for t in build_assistant_tools()]
        assert names[-1] == "search_knowledge_base"

    def test_registry_excludes_kb_tool_when_disabled(self) -> None:
        """对话「使用知识库」开关关闭时工具不注入。"""
        names = [t.name for t in build_assistant_tools(use_kb=False)]
        assert "search_knowledge_base" not in names


@pytest.mark.unit
class TestSearchKnowledgeBase:
    async def test_invalid_point_type_returns_error(self) -> None:
        result = await kt.search_knowledge_base.ainvoke(
            {"query": "均线", "point_type": "quote"}
        )
        assert "error" in result
        assert "concept" in result["error"]

    async def test_unknown_source_lists_available(self) -> None:
        ctx = _SessionCtx(
            [
                _ExecResult(first=None),
                _ExecResult(scalars_all=["价值投资课", "缠论原著"]),
            ]
        )
        with patch.object(kt, "AsyncSessionLocal", lambda: ctx):
            result = await kt.search_knowledge_base.ainvoke(
                {"query": "均线", "source": "不存在"}
            )
        assert "error" in result
        assert "价值投资课、缠论原著" in result["error"]

    async def test_course_card_citation_with_timecode(self) -> None:
        ctx = _SessionCtx(
            [_ExecResult(first=SimpleNamespace(id=1, name="价值投资课"))]
        )
        response = KbSearchResponse(query="均线", points=[_course_hit()])
        with (
            patch.object(kt, "AsyncSessionLocal", lambda: ctx),
            patch.object(kt.search_service, "search", AsyncMock(return_value=response)),
        ):
            result = await kt.search_knowledge_base.ainvoke(
                {"query": "均线", "source": "价值投资课", "include_media": True}
            )
        card = result["points"][0]
        assert card["type"] == "方法"
        assert card["title"] == "均线金叉加仓纪律"
        assert card["citation"] == "《价值投资课》 第3集 05:30-06:10（第二章/均线系统）"
        assert card["media"] == {
            "id": 2,
            "kind": "video",
            "seek_ms": 330_000,
            "title": "第3课 均线系统",
            "episode_no": 3,
        }
        assert card["body"].endswith("…")
        assert len(card["body"]) == 501
        assert card["term_definition"].startswith("金叉：")
        assert card["excerpt"].startswith("你看这个金叉")
        assert result["source"] == "价值投资课"

    async def test_book_card_citation_with_pages(self) -> None:
        ctx = _SessionCtx([_ExecResult(first=SimpleNamespace(id=2, name="缠中说禅"))])
        response = KbSearchResponse(query="中枢", points=[_book_hit()])
        with (
            patch.object(kt, "AsyncSessionLocal", lambda: ctx),
            patch.object(kt.search_service, "search", AsyncMock(return_value=response)),
        ):
            result = await kt.search_knowledge_base.ainvoke(
                {"query": "中枢", "source": "缠中说禅", "include_media": True}
            )
        assert (
            result["points"][0]["citation"] == "《缠中说禅》 第45-47页（第一册）"
        )
        assert result["points"][0]["media"] == {
            "id": 5,
            "kind": "book",
            "page_no": 45,
            "title": "缠中说禅",
        }

    async def test_media_omitted_by_default(self) -> None:
        """默认（include_media=False）只出 citation 不出 media 引用。"""
        ctx = _SessionCtx([_ExecResult(rows=[(1, "价值投资课")])])
        segment = KbSearchSegmentHit(
            id=20,
            source_id=1,
            media_id=2,
            media_kind="video",
            episode_no=3,
            media_title="第3课 均线系统",
            text="这一段我们讲均线粘合后的方向选择。" * 30,
            start_ms=600_000,
            end_ms=660_000,
            score=0.01,
        )
        response = KbSearchResponse(query="均线", points=[_course_hit()], segments=[segment])
        with (
            patch.object(kt, "AsyncSessionLocal", lambda: ctx),
            patch.object(kt.search_service, "search", AsyncMock(return_value=response)),
        ):
            result = await kt.search_knowledge_base.ainvoke({"query": "均线"})
        assert result["source"] == "全部知识库"
        assert result["points"][0]["citation"].startswith("《价值投资课》 第3集")
        assert "media" not in result["points"][0]
        assert result["segments"][0]["citation"] == "《价值投资课》 第3集 10:00-11:00"
        assert "media" not in result["segments"][0]
        assert result["segments"][0]["text"].endswith("…")

    async def test_all_source_hits_resolve_source_name(self) -> None:
        ctx = _SessionCtx([_ExecResult(rows=[(1, "价值投资课")])])
        segment = KbSearchSegmentHit(
            id=20,
            source_id=1,
            media_id=2,
            media_kind="video",
            episode_no=3,
            media_title="第3课 均线系统",
            text="这一段我们讲均线粘合后的方向选择。" * 30,
            start_ms=600_000,
            end_ms=660_000,
            score=0.01,
        )
        response = KbSearchResponse(query="均线", points=[_course_hit()], segments=[segment])
        with (
            patch.object(kt, "AsyncSessionLocal", lambda: ctx),
            patch.object(kt.search_service, "search", AsyncMock(return_value=response)),
        ):
            result = await kt.search_knowledge_base.ainvoke(
                {"query": "均线", "include_media": True}
            )
        assert result["source"] == "全部知识库"
        assert result["points"][0]["citation"].startswith("《价值投资课》 第3集")
        assert result["segments"][0]["citation"] == "《价值投资课》 第3集 10:00-11:00"
        assert result["segments"][0]["media"]["id"] == 2
        assert result["segments"][0]["media"]["seek_ms"] == 600_000
        assert result["segments"][0]["text"].endswith("…")

    async def test_degraded_note_and_empty_hint(self) -> None:
        degraded = KbSearchResponse(query="冷门词", degraded="embedding_unavailable")
        empty = KbSearchResponse(query="冷门词")
        with (
            patch.object(
                kt, "AsyncSessionLocal", lambda: _SessionCtx([_ExecResult(rows=[])])
            ),
            patch.object(
                kt.search_service, "search", AsyncMock(return_value=degraded)
            ),
        ):
            result = await kt.search_knowledge_base.ainvoke({"query": "冷门词"})
        assert "向量检索当前不可用" in result["note"]

        with (
            patch.object(
                kt, "AsyncSessionLocal", lambda: _SessionCtx([_ExecResult(rows=[])])
            ),
            patch.object(kt.search_service, "search", AsyncMock(return_value=empty)),
        ):
            result = await kt.search_knowledge_base.ainvoke({"query": "冷门词"})
        assert "无命中" in result["note"]
