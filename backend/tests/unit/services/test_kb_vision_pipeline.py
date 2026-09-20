"""关键帧选帧管线纯函数单测（三路信号融合 / 时间窗合并 / aHash 去重 / 配额）。"""

import pytest

from app.services.kb import vision_pipeline as vpipe

pytestmark = pytest.mark.unit


class TestParseSceneTimes:
    def test_extracts_pts_time_sorted_dedup(self) -> None:
        stderr = "\n".join(
            [
                "[Parsed_showinfo_1 @ 0x0] n:0 pts_time:12.5 pts:123",
                "[Parsed_showinfo_1 @ 0x0] n:1 pts_time:3.25",
                "[Parsed_showinfo_1 @ 0x0] n:2 pts_time:12.5",
            ]
        )
        assert vpipe.parse_scene_times(stderr) == [3.25, 12.5]

    def test_empty_stderr(self) -> None:
        assert vpipe.parse_scene_times("no matches here") == []


class TestGuideTimestamps:
    def test_midpoint_of_matching_sentences(self) -> None:
        segments = [
            (0, 60_000, "大盘这里你看这条线的支撑"),
            (60_000, 120_000, "基本面没有变化"),
            (120_000, 180_000, "如图所示这个中枢延伸"),
        ]
        assert vpipe.guide_timestamps(segments) == [30.0, 150.0]

    def test_skips_missing_timecodes(self) -> None:
        segments = [(None, None, "你看这根均线"), (0, 10_000, "普通句")]
        assert vpipe.guide_timestamps(segments) == []


class TestPlanFrames:
    def test_window_merge_keeps_higher_priority(self) -> None:
        # 3s 窗口内 scene(31) 与 fixed(33) 冲突 → 保留 scene
        frames = vpipe.plan_frames(
            scene_times=[31.0],
            fixed_interval_seconds=33,
            duration_seconds=120.0,
            guide_times=[],
            merge_window_seconds=5.0,
            max_frames=120,
        )
        near = [f for f in frames if 28 <= f.start_seconds <= 36]
        assert len(near) == 1
        assert near[0].signal == "scene"

    def test_guide_beats_scene_in_window(self) -> None:
        frames = vpipe.plan_frames(
            scene_times=[100.0],
            fixed_interval_seconds=0,
            duration_seconds=200.0,
            guide_times=[101.0],
            merge_window_seconds=5.0,
            max_frames=120,
        )
        assert [f.signal for f in frames] == ["guide"]
        assert frames[0].start_seconds == 101.0

    def test_out_of_range_dropped(self) -> None:
        frames = vpipe.plan_frames(
            scene_times=[10.0, 999.0],
            fixed_interval_seconds=0,
            duration_seconds=100.0,
            guide_times=[-1.0],
            merge_window_seconds=5.0,
            max_frames=120,
        )
        assert [f.start_seconds for f in frames] == [10.0]

    def test_fixed_interval_generation(self) -> None:
        frames = vpipe.plan_frames(
            scene_times=[],
            fixed_interval_seconds=60,
            duration_seconds=190.0,
            guide_times=[],
            merge_window_seconds=5.0,
            max_frames=120,
        )
        assert [f.start_seconds for f in frames] == [60.0, 120.0, 180.0]

    def test_cap_keeps_by_priority(self) -> None:
        scene_times = [float(t) for t in range(100, 200, 10)]
        guide_times = [5.0, 15.0]
        frames = vpipe.plan_frames(
            scene_times=scene_times,
            fixed_interval_seconds=0,
            duration_seconds=300.0,
            guide_times=guide_times,
            merge_window_seconds=5.0,
            max_frames=3,
        )
        # 两条 guide 全保留 + 场景最早一条；输出按时刻升序
        assert [(f.signal, f.start_seconds) for f in frames] == [
            ("guide", 5.0),
            ("guide", 15.0),
            ("scene", 100.0),
        ]


class TestAHash:
    def test_uniform_bright_hash_zero(self) -> None:
        # 全 255：均值=255，无字节严格大于均值 → 全 0 位
        assert vpipe.ahash(bytes([255] * 256)) == 0

    def test_half_split(self) -> None:
        gray = bytes([255] * 128 + [0] * 128)
        # 前 128 字节亮于均值（均值 127.5）→ 前 128 位全 1
        assert vpipe.ahash(gray) == ((1 << 128) - 1) << 128

    def test_short_input_returns_zero(self) -> None:
        assert vpipe.ahash(b"\x00" * 10) == 0

    def test_hamming_and_duplicate(self) -> None:
        a = 0b1010
        b = 0b1011
        assert vpipe.hamming(a, b) == 1
        assert vpipe.is_near_duplicate(a, [b], threshold=5)
        assert not vpipe.is_near_duplicate(a, [0xFFFF], threshold=5)
