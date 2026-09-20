"""抽取管线纯函数单测：开窗、时间码防线、excerpt 命中、去重与 related 回链。"""

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
) -> KbPointDraft:
    return KbPointDraft(
        title=title,
        body="正文",
        point_type="concept",
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
    def test_excerpt_hit_passes(self) -> None:
        segments = [_seg(0, 10_000, "价值投资需要安全边际。")]
        out = xpipe.validate_points([_draft(excerpt="需要安全边际")], segments)
        assert out[0].needs_review is False
        assert out[0].start_ms == 0

    def test_excerpt_miss_marks_needs_review(self) -> None:
        segments = [_seg(0, 10_000, "完全无关的内容。")]
        out = xpipe.validate_points([_draft(excerpt="凭空捏造的句子")], segments)
        assert out[0].needs_review is True

    def test_excerpt_punctuated_normalized_match(self) -> None:
        segments = [_seg(0, 10_000, "价值，投资！需要安全边际。")]
        out = xpipe.validate_points([_draft(excerpt="价值投资需要安全边际")], segments)
        assert out[0].needs_review is False

    def test_inverted_span_drops_positioning(self) -> None:
        segments = [_seg(0, 10_000, "原文句子")]
        out = xpipe.validate_points([_draft(start=9_000, end=1_000)], segments)
        assert out[0].start_ms is None and out[0].end_ms is None
        assert out[0].needs_review is True

    def test_span_clamped_into_media_duration(self) -> None:
        segments = [_seg(0, 10_000, "原文句子")]
        out = xpipe.validate_points(
            [_draft(start=-5_000, end=99_999)],
            segments,
            media_duration_ms=60_000,
        )
        assert (out[0].start_ms, out[0].end_ms) == (0, 60_000)
        assert out[0].needs_review is False

    def test_title_stripped(self) -> None:
        segments = [_seg(0, 10_000, "原文句子")]
        out = xpipe.validate_points([_draft(title="  复利效应  ")], segments)
        assert out[0].title == "复利效应"


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

    def test_needs_review_or_semantics(self) -> None:
        good = xpipe.validate_points(
            [_draft(title="ROE", excerpt="原文句子")], [_seg(0, 10_000, "原文句子")]
        )
        bad = xpipe.validate_points(
            [_draft(title="R.O.E", excerpt="未命中")], [_seg(0, 10_000, "原文句子")]
        )
        out = xpipe.dedup_points(good + bad)
        assert len(out) == 1
        assert out[0].needs_review is True

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
            "title", "body", "point_type", "term_definition",
            "applicable_scene", "excerpt", "start_ms", "end_ms", "related_titles",
        }

    def test_missing_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            KbPointDraft(
                title="t", body="b", point_type="concept", term_definition=None,
                applicable_scene=None, excerpt="e", start_ms=None, end_ms=None,
            )
