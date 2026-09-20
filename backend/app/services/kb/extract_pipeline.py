"""知识点抽取管线纯函数：窗口规划、幻觉防线校验、去重与章节树 id 赋值。

无 IO、无 ORM——输入输出为纯数据（pydantic LLM 契约与 dataclass），
便于单测钉死三层防线边界行为。时间单位统一毫秒（int）。
"""

import re
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from typing import Any

from app.constants.kb import (
    KB_EXTRACT_WINDOW_OVERLAP_SEGMENTS,
    KB_EXTRACT_WINDOW_SECONDS,
)
from app.schemas.kb import ChapterTreeDraft, KbPointDraft

#: 无时间码素材（电子书页级分段）按分段数开窗
_BOOK_WINDOW_SEGMENTS = 40

_PUNCT_RE = re.compile(r"[\W_]+", re.UNICODE)


@dataclass(slots=True)
class WindowSegment:
    """窗口内的最小分段视图（与 ORM 行解耦）。"""

    text: str
    start_ms: int | None
    end_ms: int | None


@dataclass(slots=True)
class ValidatedPoint:
    """通过防线校验的候选知识点（related_titles 留待服务层回链成 id）。

    ``reasons`` 为升级人工的理由清单（空 = 可自动发布）。
    """

    point_type: str
    title: str
    body: str
    confidence: str
    chapter_path: list[str]
    term_definition: str | None
    applicable_scene: str | None
    excerpt: str
    start_ms: int | None
    end_ms: int | None
    reasons: list[str]
    related_titles: list[str]

    @property
    def needs_review(self) -> bool:
        return bool(self.reasons)


def normalize_title(title: str) -> str:
    """标题归一化（去空白/标点、lower）——窗口去重与 related 回链的匹配键。"""
    return _PUNCT_RE.sub("", title).lower()


def plan_windows(
    segments: list[WindowSegment],
    *,
    max_seconds: int = KB_EXTRACT_WINDOW_SECONDS,
    overlap: int = KB_EXTRACT_WINDOW_OVERLAP_SEGMENTS,
) -> list[list[WindowSegment]]:
    """按时间码滑窗：累积至 ≤max_seconds 成窗，下窗回带 overlap 段上下文。

    无时间码素材（书的页级分段）退化为固定分段数开窗。
    """
    if not segments:
        return []
    if segments[0].start_ms is None:
        return [
            segments[i : i + _BOOK_WINDOW_SEGMENTS]
            for i in range(0, len(segments), _BOOK_WINDOW_SEGMENTS)
        ]
    max_ms = max_seconds * 1000
    windows: list[list[WindowSegment]] = []
    current: list[WindowSegment] = []
    for seg in segments:
        if current:
            start = current[0].start_ms or 0
            end = seg.end_ms or seg.start_ms or 0
            if end - start > max_ms:
                windows.append(current)
                current = list(current[-overlap:]) if overlap > 0 else []
        current.append(seg)
    if current and (
        not windows or [s.text for s in current] != [s.text for s in windows[-1]]
    ):
        windows.append(current)
    return windows


#: LLM 引用讲课时以省略号删节（「……」/「...」），按段拆开逐段锚定
_ELLIPSIS_RE = re.compile(r"…+|\.{3,}")


def anchor_excerpt(excerpt: str, texts: list[str]) -> str | None:
    """摘录锚定：在全文归一化拼接中定位，返回覆盖命中的文稿原文段。

    含省略号的摘录按段拆开**逐段顺序锚定**（段间以「……」回接）——删节
    引用的每一部分仍是逐字原文，溯源不降级。命中片段经字符偏移映射回
    句级分段区间（长度不限，长引用不升级）；标点/空白差异由归一化吸收；
    任一段未命中返回 None（幻觉信号）。
    """
    chunks = [c for c in _ELLIPSIS_RE.split(excerpt) if _PUNCT_RE.sub("", c)]
    if not chunks:
        return None
    normed = [_PUNCT_RE.sub("", t) for t in texts]
    offsets = [0]
    for t in normed:
        offsets.append(offsets[-1] + len(t))
    whole = "".join(normed)
    parts: list[str] = []
    seg_cursor = 0
    for chunk in chunks:
        target = _PUNCT_RE.sub("", chunk)
        at = whole.find(target, offsets[seg_cursor])
        if at < 0:
            return None
        i = bisect_right(offsets, at) - 1
        j = bisect_left(offsets, at + len(target))
        parts.append("".join(texts[i:j]))
        seg_cursor = j
    return "……".join(parts)


def validate_points(
    raw_points: list[KbPointDraft],
    segments: list[WindowSegment],
    *,
    media_duration_ms: int = 0,
    valid_chapters: set[tuple[str, ...]] | None = None,
) -> list[ValidatedPoint]:
    """防线校验 + 升级理由收集（reasons 空 = 可自动发布）。

    - 时间码越界 clamp（end≤start 弃定位）；时间码素材无定位升级
    - 摘录锚定：命中替换为原文，全 miss 升级（幻觉风险）
    - 章节链校验：悬空引用修剪到合法前缀，空/未归章升级
    - confidence≠high 升级；case 型任何理由叠加时显式标注
    """
    chapters = valid_chapters or set()
    timed_media = bool(segments) and segments[0].start_ms is not None
    out: list[ValidatedPoint] = []
    for p in raw_points:
        start, end = _clamp_span(p.start_ms, p.end_ms, media_duration_ms)
        reasons: list[str] = []
        if p.start_ms is not None and start is None:
            reasons.append("时间码无效已弃定位")
        elif timed_media and start is None:
            reasons.append("缺少时间码定位")
        anchored = anchor_excerpt(p.excerpt, [s.text for s in segments])
        if anchored is None:
            reasons.append("摘录未命中文稿（幻觉风险）")
        path: list[str] = []
        if chapters:
            path = valid_chapter_prefix(p.chapter_path, chapters)
            if not p.chapter_path:
                reasons.append("未归章")
            elif not path:
                reasons.append("章节引用无效")
        elif p.chapter_path:
            reasons.append("无目录树可归章")
        if p.confidence != "high":
            reasons.append(f"模型置信度 {p.confidence}")
        if p.point_type == "case" and reasons:
            reasons.append("案例卡需人工复核")
        out.append(
            ValidatedPoint(
                point_type=p.point_type,
                title=p.title.strip() or p.title,
                body=p.body,
                confidence=p.confidence,
                chapter_path=path,
                term_definition=p.term_definition,
                applicable_scene=p.applicable_scene,
                excerpt=anchored if anchored is not None else p.excerpt,
                start_ms=start,
                end_ms=end,
                reasons=reasons,
                related_titles=list(p.related_titles),
            )
        )
    return out


def _clamp_span(
    start: int | None, end: int | None, media_duration_ms: int
) -> tuple[int | None, int | None]:
    """时间码 clamp 进 [0, 时长]；end≤start 弃定位（返回 null 对）。"""
    if start is None or end is None:
        return start, end
    if media_duration_ms > 0:
        start = min(max(start, 0), media_duration_ms)
        end = min(max(end, 0), media_duration_ms)
    if end <= start:
        return None, None
    return start, end


def dedup_points(points: list[ValidatedPoint]) -> list[ValidatedPoint]:
    """跨窗口去重：归一化标题相同视为同一知识点，时间码取并集、needs_review 取或。"""
    out: list[ValidatedPoint] = []
    by_key: dict[str, ValidatedPoint] = {}
    for point in points:
        key = normalize_title(point.title)
        seen = by_key.get(key)
        if seen is None:
            by_key[key] = point
            out.append(point)
            continue
        if point.start_ms is not None:
            seen.start_ms = (
                point.start_ms
                if seen.start_ms is None
                else min(seen.start_ms, point.start_ms)
            )
        if point.end_ms is not None:
            seen.end_ms = (
                point.end_ms if seen.end_ms is None else max(seen.end_ms, point.end_ms)
            )
        seen.reasons = list(dict.fromkeys(seen.reasons + point.reasons))
    return out


def resolve_related(
    related_titles: list[str], title_to_id: dict[str, int]
) -> list[int]:
    """防线③：related_titles 按归一化标题回链同库知识点 id，未匹配剔除。"""
    ids: list[int] = []
    for title in related_titles:
        point_id = title_to_id.get(normalize_title(title))
        if point_id is not None and point_id not in ids:
            ids.append(point_id)
    return ids


def assign_chapter_ids(tree: ChapterTreeDraft) -> list[dict[str, Any]]:
    """目录树草稿落库形态：按位置生成稳定 id（"1"/"1.2"，draft 生命周期内不变）。"""
    return [_node_dict(node, str(i)) for i, node in enumerate(tree.nodes, start=1)]


def _node_dict(node: Any, node_id: str) -> dict[str, Any]:
    return {
        "id": node_id,
        "title": node.title,
        "children": [
            _node_dict(child, f"{node_id}.{j}")
            for j, child in enumerate(node.children, start=1)
        ],
    }


def chapter_id_paths(nodes: list[dict[str, Any]] | None) -> set[tuple[str, ...]]:
    """收集树中全部合法节点 id 链（根到节点，含单 id 顶层链）。"""
    paths: set[tuple[str, ...]] = set()

    def walk(children: list[dict[str, Any]] | None, prefix: tuple[str, ...]) -> None:
        for node in children or []:
            path = (*prefix, str(node["id"]))
            paths.add(path)
            walk(node.get("children"), path)

    walk(nodes, ())
    return paths


def valid_chapter_prefix(
    path: list[str] | None, valid: set[tuple[str, ...]]
) -> list[str]:
    """保留最长合法链前缀（树重发布后清理悬空引用 / 归章输出校验共用）。"""
    ids = [str(p) for p in (path or [])]
    for size in range(len(ids), 0, -1):
        if tuple(ids[:size]) in valid:
            return ids[:size]
    return []
