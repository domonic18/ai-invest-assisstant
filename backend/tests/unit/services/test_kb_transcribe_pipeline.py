"""转写流水线纯函数与 asr_client 解析单测（无 IO）。"""

import pytest

from app.services.kb import transcribe_pipeline as pipeline
from app.services.kb.asr_client import normalize_ms, parse_verbose_json
from app.services.kb.transcribe_pipeline import ChunkAsr, Sentence

pytestmark = pytest.mark.unit


# ---------- parse_silencedetect ----------


def test_parse_silencedetect_pairs() -> None:
    stderr = (
        "[silencedetect @ 0x0] silence_start: 120.5\n"
        "[silencedetect @ 0x0] silence_end: 121.3 | silence_duration: 0.8\n"
        "[silencedetect @ 0x0] silence_start: 300\n"
        "[silencedetect @ 0x0] silence_end: 300.6 | silence_duration: 0.6\n"
    )
    assert pipeline.parse_silencedetect(stderr) == [(120.5, 121.3), (300.0, 300.6)]


def test_parse_silencedetect_unclosed_tail_ignored() -> None:
    stderr = "[silencedetect @ 0x0] silence_start: 400\n"
    assert pipeline.parse_silencedetect(stderr) == []


# ---------- plan_chunks ----------


def test_plan_chunks_cuts_at_silence_midpoints() -> None:
    silences = [(479.0, 481.0), (959.0, 961.0)]
    chunks = pipeline.plan_chunks(1200.0, silences, max_chunk=480.0)
    assert chunks[0] == (0.0, 480.0)  # 静音中点 480
    assert chunks[1] == (480.0, 960.0)
    assert chunks[-1] == (960.0, 1200.0)
    assert all(end - start <= 480.0 for start, end in chunks)


def test_plan_chunks_fixed_fallback_without_silence() -> None:
    chunks = pipeline.plan_chunks(1000.0, [], max_chunk=480.0)
    assert chunks == [(0.0, 480.0), (480.0, 960.0), (960.0, 1000.0)]


def test_plan_chunks_gap_over_limit_splits_fixed() -> None:
    # 单个静音间距 1000s > 480s：中点前定长兜底
    chunks = pipeline.plan_chunks(1200.0, [(999.0, 1001.0)], max_chunk=480.0)
    assert all(end - start <= 480.0 + 1e-6 for start, end in chunks)
    span = sum(end - start for start, end in chunks)
    assert span == pytest.approx(1200.0)


def test_plan_chunks_empty_duration() -> None:
    assert pipeline.plan_chunks(0, []) == []


# ---------- merge / group ----------


def test_merge_chunks_applies_offsets_and_sorts() -> None:
    chunks = [
        ChunkAsr(0, 480, [Sentence(0, 2000, "b"), Sentence(0, 1000, "a")]),
        ChunkAsr(480, 900, [Sentence(0, 1500, "c")]),
    ]
    merged = pipeline.merge_chunks(chunks)
    assert [s.text for s in merged] == ["a", "b", "c"]
    assert merged[2].start_ms == 480_000


def test_merge_drops_empty_sentences() -> None:
    chunks = [ChunkAsr(0, 10, [Sentence(0, 1000, "  ")])]
    assert pipeline.merge_chunks(chunks) == []


def test_group_sentences_bundles_within_limit() -> None:
    sentences = [
        Sentence(0, 10_000, "一"),
        Sentence(10_000, 20_000, "二"),
        Sentence(20_000, 25_000, "三"),
        Sentence(25_000, 40_000, "四"),
    ]
    grouped = pipeline.group_sentences(sentences, max_seconds=30)
    assert [g.text for g in grouped] == ["一二三", "四"]
    assert grouped[0].start_ms == 0 and grouped[0].end_ms == 25_000


def test_group_sentences_splits_overlong_single() -> None:
    long = Sentence(0, 60_000, "字" * 12)
    grouped = pipeline.group_sentences([long], max_seconds=30)
    assert len(grouped) == 2
    assert all(g.end_ms - g.start_ms <= 30_000 for g in grouped)
    assert "".join(g.text for g in grouped) == "字" * 12


# ---------- asr_client 解析 ----------


def test_normalize_ms_threshold() -> None:
    assert normalize_ms(9.5) == 9500
    assert normalize_ms(9500) == 9500
    assert normalize_ms(120.5) == 120_500


def test_parse_verbose_json_sentences_key() -> None:
    payload = {
        "base_resp": {"status_code": 0},
        "sentences": [
            {"start_time": 0, "end_time": 2.5, "text": "你好"},
            {"start_time": 2500, "end_time": 4800, "text": "市场"},
        ],
    }
    sentences = parse_verbose_json(payload)
    assert [s.text for s in sentences] == ["你好", "市场"]
    assert sentences[0].end_ms == 2500
    assert sentences[1].start_ms == 2500


def test_parse_verbose_json_segments_key_and_missing_fields() -> None:
    payload = {
        "segments": [
            {"start": 1.0, "end": 2.0, "text": "甲"},
            {"text": "缺时间戳"},
        ]
    }
    sentences = parse_verbose_json(payload)
    assert [s.text for s in sentences] == ["甲"]


def test_parse_verbose_json_no_items() -> None:
    assert parse_verbose_json({"text": "x"}) == []
