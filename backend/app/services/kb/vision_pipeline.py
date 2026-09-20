"""关键帧选帧纯函数（批次 I，无 IO）。

三路信号互补：

1. 场景切换（主讲切 PPT/切屏）：``ffmpeg select='gt(scene,T)' + showinfo``
   的 stderr 按 ``pts_time`` 解析；
2. 定长兜底（画面渐变型课程的保底采样）；
3. 文稿引导（视觉指涉句取句中点——盘面讲解类课程的关键帧往往无场景突变，
   只有此路能命中「画线瞬间」）。

融合：时间窗合并（窗口内保留信号优先级最高者，文稿 > 场景 > 定长）→
aHash 感知哈希（16×16 灰度 rawvideo，纯 Python 汉明距离）滤近重复 →
单集硬上限裁剪（超限按优先级保留）。
"""

import re
from dataclasses import dataclass

from app.constants.kb import KB_VISION_GUIDE_PATTERNS

_SHOWINFO_PTS_TIME = re.compile(r"pts_time:([0-9]+(?:\.[0-9]+)?)")

# 信号优先级：数值越小越优先（融合保留与配额裁剪同序）
_SIGNAL_PRIORITY = {"guide": 0, "scene": 1, "fixed": 2}


@dataclass(slots=True)
class FrameCandidate:
    """选帧候选：抽取时刻（秒）与命中的信号路。"""

    start_seconds: float
    signal: str


@dataclass(slots=True)
class FrameHash:
    """带 aHash 的选帧结果（服务层用于近重复过滤）。"""

    start_seconds: float
    signal: str
    phash: int


def parse_scene_times(stderr: str) -> list[float]:
    """解析 ffmpeg showinfo 输出中的场景切换时刻（秒，升序去重）。"""
    times = {float(m.group(1)) for m in _SHOWINFO_PTS_TIME.finditer(stderr)}
    return sorted(times)


def guide_timestamps(
    segments: list[tuple[int | None, int | None, str]],
) -> list[float]:
    """视觉指涉句的句中点时刻（秒）。

    Args:
        segments: ``(start_ms, end_ms, text)`` 序列（时间码可空则跳过）。
    """
    times: list[float] = []
    for start_ms, end_ms, text in segments:
        if start_ms is None or end_ms is None or end_ms <= start_ms:
            continue
        if not any(pattern in text for pattern in KB_VISION_GUIDE_PATTERNS):
            continue
        times.append((start_ms + end_ms) / 2000.0)
    return times


def plan_frames(
    scene_times: list[float],
    fixed_interval_seconds: int,
    duration_seconds: float,
    guide_times: list[float],
    merge_window_seconds: float,
    max_frames: int,
) -> list[FrameCandidate]:
    """三路信号融合为一组去重选帧（时刻升序）。

    Args:
        scene_times: 场景切换时刻（秒）。
        fixed_interval_seconds: 定长兜底采样间隔（≤0 关闭该路）。
        duration_seconds: 素材时长（秒，越界候选被丢弃）。
        guide_times: 文稿引导时刻（秒）。
        merge_window_seconds: 时间窗合并阈值（窗内保留优先级最高者）。
        max_frames: 单集硬上限（超限按信号优先级裁剪）。
    """
    candidates: list[FrameCandidate] = [
        *[FrameCandidate(t, "guide") for t in guide_times if 0 <= t <= duration_seconds],
        *[FrameCandidate(t, "scene") for t in scene_times if 0 <= t <= duration_seconds],
    ]
    if fixed_interval_seconds > 0:
        candidates.extend(
            FrameCandidate(float(t), "fixed")
            for t in range(fixed_interval_seconds, int(duration_seconds),
                           fixed_interval_seconds)
        )

    # 时间窗合并：按时刻排序后扫窗，窗内保留优先级最高（并列取更早）
    candidates.sort(key=lambda c: c.start_seconds)
    merged: list[FrameCandidate] = []
    window: list[FrameCandidate] = []

    def _flush() -> None:
        if window:
            merged.append(min(window, key=lambda c: (_SIGNAL_PRIORITY[c.signal],
                                                     c.start_seconds)))
            window.clear()

    for candidate in candidates:
        if window and candidate.start_seconds - window[0].start_seconds > merge_window_seconds:
            _flush()
        window.append(candidate)
    _flush()

    # 配额裁剪：按信号优先级保留，再恢复时刻升序
    merged.sort(key=lambda c: (_SIGNAL_PRIORITY[c.signal], c.start_seconds))
    kept = merged[:max_frames]
    kept.sort(key=lambda c: c.start_seconds)
    return kept


def ahash(gray16: bytes) -> int:
    """16×16 灰度 rawvideo（256 字节）→ 64 位 aHash（亮于均值为 1）。"""
    if len(gray16) < 256:
        return 0
    mean = sum(gray16) / 256
    bits = 0
    for byte in gray16[:256]:
        bits = (bits << 1) | (1 if byte > mean else 0)
    return bits


def hamming(a: int, b: int) -> int:
    """两个 aHash 的汉明距离。"""
    return (a ^ b).bit_count()


def is_near_duplicate(phash: int, kept_hashes: list[int], threshold: int) -> bool:
    """与任一已保留帧的汉明距离 ≤ 阈值即视为近重复。"""
    return any(hamming(phash, kept) <= threshold for kept in kept_hashes)
