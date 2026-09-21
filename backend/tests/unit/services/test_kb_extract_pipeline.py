"""抽取管线纯函数单测：开窗、升级门（时间码/摘录锚定/归章/置信度）、
去重与 related 回链。"""

from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas.kb import ChapterNodeDraft, ChapterTreeDraft, KbPointDraft
from app.services.kb import extract_pipeline as xpipe
from app.services.kb.extract_pipeline import WindowSegment

pytestmark = pytest.mark.unit


def _seg(start: int, end: int, text: str = "句") -> WindowSegment:
    return WindowSegment(text=text, start_ms=start, end_ms=end)


def _draft(
    title: str = "复利",
    *,
    excerpt: str = "原文句子",
    start: int | None = 0,
    end: int | None = 10_000,
    related: list[str] | None = None,
    confidence: str = "high",
    chapter_path: list[str] | None = None,
    point_type: str = "concept",
) -> KbPointDraft:
    return KbPointDraft(
        title=title,
        body="正文",
        point_type=point_type,
        confidence=confidence,
        chapter_path=chapter_path,
        term_definition=None,
        applicable_scene=None,
        excerpt=excerpt,
        start_ms=start,
        end_ms=end,
        related_titles=related or [],
    )


class TestNormalizeTitle:
    def test_strips_punct_whitespace_and_lowers(self) -> None:
        assert xpipe.normalize_title("  ROE： 净资产！收益率 ") == "roe净资产收益率"

    def test_stable_for_same_semantics(self) -> None:
        assert xpipe.normalize_title("安全边际!") == xpipe.normalize_title("安全边际。")


class TestPlanWindows:
    def test_empty(self) -> None:
        assert xpipe.plan_windows([]) == []

    def test_600s_cap_with_one_segment_overlap(self) -> None:
        # 10 段 × 120s：600s 封顶 → 5 段一窗，下窗回带 1 段
        segments = [_seg(i * 120_000, (i + 1) * 120_000, f"s{i}") for i in range(10)]
        windows = xpipe.plan_windows(segments)
        assert [len(w) for w in windows] == [5, 5, 2]
        # 窗口 2 首段是窗口 1 末段（overlap）
        assert windows[1][0].text == "s4"
        assert windows[2][0].text == "s8"

    def test_single_oversized_segment_forms_own_window(self) -> None:
        segments = [_seg(0, 900_000, "超长段"), _seg(900_000, 960_000, "尾段")]
        windows = xpipe.plan_windows(segments)
        # 超长段自成一窗；同时作为 overlap 上下文回带到下一窗
        assert [len(w) for w in windows] == [1, 2]
        assert windows[0][0].text == "超长段"
        assert windows[1][0].text == "超长段"

    def test_book_fallback_fixed_segment_windows(self) -> None:
        segments = [WindowSegment(text=f"p{i}", start_ms=None, end_ms=None) for i in range(45)]
        windows = xpipe.plan_windows(segments)
        assert [len(w) for w in windows] == [40, 5]


class TestValidatePoints:
    def test_clean_point_has_no_reasons(self) -> None:
        segments = [_seg(0, 10_000, "价值投资需要安全边际。")]
        out = xpipe.validate_points([_draft(excerpt="需要安全边际")], segments)
        assert out[0].reasons == []
        assert out[0].needs_review is False
        assert out[0].start_ms == 0

    def test_excerpt_hit_replaced_with_transcript_original(self) -> None:
        segments = [
            _seg(0, 10_000, "复利，就是利滚利。"),
            _seg(10_000, 20_000, "下一句。"),
        ]
        out = xpipe.validate_points([_draft(excerpt="复利 就是利滚利")], segments)
        assert out[0].reasons == []
        assert out[0].excerpt == "复利，就是利滚利。"

    def test_excerpt_anchor_spans_consecutive_segments(self) -> None:
        segments = [
            _seg(0, 10_000, "第一句。"),
            _seg(10_000, 20_000, "第二句，"),
            _seg(20_000, 30_000, "第三句。"),
        ]
        out = xpipe.validate_points([_draft(excerpt="第二句，第三句")], segments)
        assert out[0].reasons == []
        assert out[0].excerpt == "第二句，第三句。"

    def test_excerpt_miss_escalates_and_keeps_original(self) -> None:
        segments = [_seg(0, 10_000, "完全无关的内容。")]
        out = xpipe.validate_points([_draft(excerpt="凭空捏造的句子")], segments)
        assert "摘录未命中文稿（幻觉风险）" in out[0].reasons
        # 未命中保留 LLM 摘录原样，供人工对照文稿核查
        assert out[0].excerpt == "凭空捏造的句子"

    def test_ellipsis_excerpt_anchors_each_chunk_in_order(self) -> None:
        segments = [
            _seg(0, 10_000, "第一句。"),
            _seg(10_000, 20_000, "第二句，"),
            _seg(20_000, 30_000, "第三句。"),
            _seg(30_000, 40_000, "第四句。"),
        ]
        out = xpipe.validate_points(
            [_draft(excerpt="第二句，……第四句")], segments
        )
        assert out[0].reasons == []
        assert out[0].excerpt == "第二句，……第四句。"

    def test_ellipsis_excerpt_one_chunk_miss_escalates(self) -> None:
        segments = [_seg(0, 10_000, "第一句。"), _seg(10_000, 20_000, "第二句。")]
        out = xpipe.validate_points(
            [_draft(excerpt="第一句。……捏造的片段")], segments
        )
        assert "摘录未命中文稿（幻觉风险）" in out[0].reasons

    def test_ellipsis_excerpt_chunks_must_not_reorder_backwards(self) -> None:
        segments = [_seg(0, 10_000, "第一句。"), _seg(10_000, 20_000, "第二句。")]
        # 逆序引用（后句在前）不允许回跳匹配
        out = xpipe.validate_points(
            [_draft(excerpt="第二句。……第一句")], segments
        )
        assert "摘录未命中文稿（幻觉风险）" in out[0].reasons

    def test_long_quote_anchors_without_span_cap(self) -> None:
        # 讲师对概念的长篇阐释（>3 句）同样是合法摘录，不因长度升级
        segments = [_seg(i * 10_000, (i + 1) * 10_000, f"第{i}句。") for i in range(6)]
        out = xpipe.validate_points(
            [_draft(excerpt="第1句。第2句。第3句。第4句。第5句。")], segments
        )
        assert out[0].reasons == []
        assert out[0].excerpt == "第1句。第2句。第3句。第4句。第5句。"

    def test_inverted_span_drops_positioning(self) -> None:
        segments = [_seg(0, 10_000, "原文句子")]
        out = xpipe.validate_points([_draft(start=9_000, end=1_000)], segments)
        assert out[0].start_ms is None and out[0].end_ms is None
        assert "时间码无效已弃定位" in out[0].reasons

    def test_span_clamped_into_media_duration(self) -> None:
        segments = [_seg(0, 10_000, "原文句子")]
        out = xpipe.validate_points(
            [_draft(start=-5_000, end=99_999)],
            segments,
            media_duration_ms=60_000,
        )
        assert (out[0].start_ms, out[0].end_ms) == (0, 60_000)
        assert out[0].reasons == []

    def test_title_stripped(self) -> None:
        segments = [_seg(0, 10_000, "原文句子")]
        out = xpipe.validate_points([_draft(title="  复利效应  ")], segments)
        assert out[0].title == "复利效应"

    def test_medium_confidence_escalates(self) -> None:
        segments = [_seg(0, 10_000, "原文句子")]
        out = xpipe.validate_points([_draft(confidence="medium")], segments)
        assert out[0].reasons == ["模型置信度 medium"]

    def test_timed_media_requires_span_but_book_not(self) -> None:
        timed = [_seg(0, 10_000, "原文句子")]
        out = xpipe.validate_points([_draft(start=None, end=None)], timed)
        assert "缺少时间码定位" in out[0].reasons

        book = [WindowSegment(text="原文句子", start_ms=None, end_ms=None)]
        out = xpipe.validate_points([_draft(start=None, end=None)], book)
        assert out[0].reasons == []

    def test_case_card_with_reason_adds_case_review(self) -> None:
        segments = [_seg(0, 10_000, "无关内容。")]
        out = xpipe.validate_points(
            [_draft(excerpt="捏造", point_type="case")], segments
        )
        assert "摘录未命中文稿（幻觉风险）" in out[0].reasons
        assert "案例卡需人工复核" in out[0].reasons

    def test_clean_case_card_not_flagged(self) -> None:
        segments = [_seg(0, 10_000, "原文句子")]
        out = xpipe.validate_points([_draft(point_type="case")], segments)
        assert out[0].reasons == []


def _tree() -> list[dict[str, Any]]:
    return [
        {
            "id": "1",
            "title": "价值篇",
            "children": [{"id": "1.1", "title": "复利", "children": []}],
        },
        {"id": "2", "title": "估值篇", "children": []},
    ]


class TestChapterGates:
    def test_valid_path_kept(self) -> None:
        out = xpipe.validate_points(
            [_draft(chapter_path=["1", "1.1"])],
            [_seg(0, 10_000, "原文句子")],
            valid_chapters=xpipe.chapter_id_paths(_tree()),
        )
        assert out[0].chapter_path == ["1", "1.1"]
        assert out[0].reasons == []

    def test_dangling_tail_pruned_to_valid_prefix(self) -> None:
        # 前缀仍合法：归到粗粒度章节即可，不升级（人工可后续修订细化）
        out = xpipe.validate_points(
            [_draft(chapter_path=["1", "9.9"])],
            [_seg(0, 10_000, "原文句子")],
            valid_chapters=xpipe.chapter_id_paths(_tree()),
        )
        assert out[0].chapter_path == ["1"]
        assert out[0].reasons == []

    def test_invalid_root_escalates(self) -> None:
        out = xpipe.validate_points(
            [_draft(chapter_path=["9"])],
            [_seg(0, 10_000, "原文句子")],
            valid_chapters=xpipe.chapter_id_paths(_tree()),
        )
        assert out[0].chapter_path == []
        assert out[0].reasons == ["章节引用无效"]

    def test_unfiled_escalates(self) -> None:
        out = xpipe.validate_points(
            [_draft(chapter_path=[])],
            [_seg(0, 10_000, "原文句子")],
            valid_chapters=xpipe.chapter_id_paths(_tree()),
        )
        assert out[0].reasons == ["未归章"]

    def test_path_without_tree_escalates(self) -> None:
        out = xpipe.validate_points(
            [_draft(chapter_path=["1"])], [_seg(0, 10_000, "原文句子")]
        )
        assert out[0].reasons == ["无目录树可归章"]


class TestValidChapterPrefix:
    def test_longest_prefix_and_misses(self) -> None:
        valid = {("1",), ("1", "1.1"), ("2",)}
        assert xpipe.valid_chapter_prefix(["1", "1.1", "x"], valid) == ["1", "1.1"]
        assert xpipe.valid_chapter_prefix(["3"], valid) == []
        assert xpipe.valid_chapter_prefix(None, valid) == []


class TestDedupPoints:
    def test_same_normalized_title_merges(self) -> None:
        first = xpipe.validate_points(
            [_draft(title="安全边际！", start=0, end=10_000)],
            [_seg(0, 10_000, "原文句子")],
        )
        second = xpipe.validate_points(
            [_draft(title="安全边际", start=30_000, end=45_000, excerpt="原文句子")],
            [_seg(30_000, 45_000, "原文句子")],
        )
        out = xpipe.dedup_points(first + second)
        assert len(out) == 1
        assert (out[0].start_ms, out[0].end_ms) == (0, 45_000)

    def test_reasons_merged_or_semantics(self) -> None:
        good = xpipe.validate_points(
            [_draft(title="ROE", excerpt="原文句子")], [_seg(0, 10_000, "原文句子")]
        )
        bad = xpipe.validate_points(
            [_draft(title="R.O.E", excerpt="未命中", confidence="medium")],
            [_seg(0, 10_000, "原文句子")],
        )
        out = xpipe.dedup_points(good + bad)
        assert len(out) == 1
        assert out[0].needs_review is True
        assert out[0].reasons == ["摘录未命中文稿（幻觉风险）", "模型置信度 medium"]

    def test_distinct_titles_kept(self) -> None:
        points = xpipe.validate_points(
            [_draft(title="复利", excerpt="原文句子"), _draft(title="护城河", excerpt="原文句子")],
            [_seg(0, 10_000, "原文句子")],
        )
        assert len(xpipe.dedup_points(points)) == 2


class TestResolveRelated:
    def test_backlink_and_drop_unmatched(self) -> None:
        title_to_id = {xpipe.normalize_title("复利"): 7, xpipe.normalize_title("护城河"): 9}
        ids = xpipe.resolve_related(["复利", "不存在的点", "复利", "护城河"], title_to_id)
        assert ids == [7, 9]


class TestAssignChapterIds:
    def test_positional_ids_stable(self) -> None:
        tree = ChapterTreeDraft(
            nodes=[
                ChapterNodeDraft(title="价值篇", children=[ChapterNodeDraft(title="复利", children=[])]),
                ChapterNodeDraft(title="估值篇", children=[]),
            ]
        )
        out = xpipe.assign_chapter_ids(tree)
        assert out[0]["id"] == "1"
        assert out[0]["children"][0]["id"] == "1.1"
        assert out[1]["id"] == "2"


class TestSchemaContract:
    """LLM 契约红线：全字段 required、无默认值（缺字段必须校验失败）。"""

    def test_extraction_result_all_required(self) -> None:
        schema = KbPointDraft.model_json_schema()
        assert set(schema["required"]) == {
            "title", "body", "point_type", "confidence", "chapter_path",
            "term_definition", "applicable_scene", "excerpt", "start_ms",
            "end_ms", "related_titles",
        }

    def test_missing_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            KbPointDraft(
                title="t", body="b", point_type="concept", term_definition=None,
                applicable_scene=None, excerpt="e", start_ms=None, end_ms=None,
            )
