"""转写流水线纯函数：silencedetect 解析、分片规划、句合并与切分。

无 IO、无 ORM——全部输入输出为纯数据，便于单测钉死边界行为。
时间单位：解析层统一毫秒（int）；ffmpeg 交互层用秒（float）。
"""

import re
from dataclasses import dataclass

#: asr-1.0 硬限 500s，留余量
MAX_CHUNK_SECONDS = 480.0
_SILENCE_START_RE = re.compile(r"silence_start:\s*([0-9.]+)")
_SILENCE_END_RE = re.compile(r"silence_end:\s*([0-9.]+)")


@dataclass(slots=True)
class Sentence:
    """句级时间码区间（全局毫秒）。"""

    start_ms: int
    end_ms: int
    text: str


@dataclass(slots=True)
class ChunkAsr:
    """单分片 ASR 结果（分片内相对毫秒时间码）。"""

    start_seconds: float
    end_seconds: float
    sentences: list[Sentence]


def parse_silencedetect(stderr: str) -> list[tuple[float, float]]:
    """解析 ffmpeg silencedetect 输出为 ``[(start, end)]`` 秒区间。

    末尾未闭合的静音区间（音频以静音收尾）忽略。
    """
    silences: list[tuple[float, float]] = []
    start: float | None = None
    for line in stderr.splitlines():
        m = _SILENCE_START_RE.search(line)
        if m:
            start = float(m.group(1))
            continue
        m = _SILENCE_END_RE.search(line)
        if m and start is not None:
            silences.append((start, float(m.group(1))))
            start = None
    return silences


def plan_chunks(
    duration_seconds: float,
    silences: list[tuple[float, float]],
    *,
    max_chunk: float = MAX_CHUNK_SECONDS,
) -> list[tuple[float, float]]:
    """规划分片：每片 ≤ max_chunk，仅在跨度将超限时于最近静音中点落刀。

    逢停顿必切会把自然语流（句间停顿每隔数秒）碎成数百个片，
    每片一次 ASR 请求——请求放大且任一片抖动即整集失败。
    静音中点只作为"必须切"时的优选切点，相邻片段合并至接近上限；
    无静音可用（或相邻静音间距仍超限）时定长兜底切。
    """
    if duration_seconds <= 0:
        return []
    mids = sorted(
        {
            (start + end) / 2
            for start, end in silences
            if 0 < (start + end) / 2 < duration_seconds
        }
    )
    bounds = [0.0, *mids, duration_seconds]

    chunks: list[tuple[float, float]] = []
    seg_start = 0.0
    prev_bound = 0.0
    for bound in bounds[1:]:
        if bound <= seg_start:
            continue
        if bound - seg_start > max_chunk:
            if prev_bound > seg_start:
                chunks.append((seg_start, prev_bound))
                seg_start = prev_bound
            while bound - seg_start > max_chunk:
                chunks.append((seg_start, seg_start + max_chunk))
                seg_start += max_chunk
            # 落刀后的余段不立即成片，继续向后累积（尾段由循环后收尾）
        prev_bound = bound
    if seg_start < duration_seconds:
        chunks.append((seg_start, duration_seconds))
    return [(round(a, 3), round(b, 3)) for a, b in chunks if b > a]


def merge_chunks(chunks: list[ChunkAsr]) -> list[Sentence]:
    """分片结果按偏移合并为全局句序列（丢弃空文本句，按 start 排序）。"""
    merged: list[Sentence] = []
    offset_ms = 0
    for chunk in chunks:
        offset_ms = int(chunk.start_seconds * 1000)
        for sent in chunk.sentences:
            text = sent.text.strip()
            if not text:
                continue
            merged.append(
                Sentence(
                    start_ms=offset_ms + sent.start_ms,
                    end_ms=offset_ms + sent.end_ms,
                    text=text,
                )
            )
    merged.sort(key=lambda s: (s.start_ms, s.end_ms))
    return merged


def group_sentences(
    sentences: list[Sentence], *, max_seconds: float
) -> list[Sentence]:
    """相邻句聚并为 ≤ max_seconds 的分段（时间戳对齐句边界）。

    单句超限时按字符占比线性内切，保证上限约束成立。
    """
    max_ms = int(max_seconds * 1000)
    segments: list[Sentence] = []
    for sent in sentences:
        if sent.end_ms - sent.start_ms > max_ms:
            segments.extend(_split_long(sent, max_ms))
            continue
        if segments:
            prev = segments[-1]
            if sent.end_ms - prev.start_ms <= max_ms:
                segments[-1] = Sentence(
                    start_ms=prev.start_ms,
                    end_ms=sent.end_ms,
                    text=f"{prev.text}{sent.text}",
                )
                continue
        segments.append(sent)
    return segments


def _split_long(sent: Sentence, max_ms: int) -> list[Sentence]:
    """超长单句按字符占比切成若干 ≤ max_ms 的段。"""
    span = sent.end_ms - sent.start_ms
    parts = max(1, -(-span // max_ms))
    size = len(sent.text) / parts
    out: list[Sentence] = []
    for i in range(parts):
        lo = round(i * size)
        hi = round((i + 1) * size)
        piece = sent.text[lo:hi].strip()
        if not piece:
            continue
        out.append(
            Sentence(
                start_ms=sent.start_ms + int(span * lo / len(sent.text)),
                end_ms=sent.start_ms + int(span * hi / len(sent.text)),
                text=piece,
            )
        )
    return out
