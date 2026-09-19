"""知识点抽取管线纯函数：窗口规划、幻觉防线校验、去重与章节树 id 赋值。

无 IO、无 ORM——输入输出为纯数据（pydantic LLM 契约与 dataclass），
便于单测钉死三层防线边界行为。时间单位统一毫秒（int）。
"""

import re
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
    """通过防线①②的候选知识点（related_titles 留待服务层回链成 id）。"""

    point_type: str
    title: str
    body: str
    term_definition: str | None
    applicable_scene: str | None
    excerpt: str
    start_ms: int | None
    end_ms: int | None
    needs_review: bool
    related_titles: list[str]


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


def match_excerpt(excerpt: str, texts: list[str]) -> bool:
    """归一化包含性判断：excerpt 须命中窗口内原文（防线②）。"""
    target = _PUNCT_RE.sub("", excerpt)
    if not target:
        return False
    for text in texts:
        if target in _PUNCT_RE.sub("", text):
            return True
    return False


def validate_points(
    raw_points: list[KbPointDraft],
    segments: list[WindowSegment],
    *,
    media_duration_ms: int = 0,
) -> list[ValidatedPoint]:
    """防线①②：时间码越界 clamp（end≤start 时弃定位并标记）、excerpt 未命中标记。

    未过防线的点不丢弃——降级为 needs_review 交人工，避免误杀真实知识点。
    """
    texts = [s.text for s in segments]
    out: list[ValidatedPoint] = []
    for p in raw_points:
        start, end = _clamp_span(p.start_ms, p.end_ms, media_duration_ms)
        bad_span = p.start_ms is not None and start is None
        needs_review = bad_span or not match_excerpt(p.excerpt, texts)
        out.append(
            ValidatedPoint(
                point_type=p.point_type,
                title=p.title.strip() or p.title,
                body=p.body,
                term_definition=p.term_definition,
                applicable_scene=p.applicable_scene,
                excerpt=p.excerpt,
                start_ms=start,
                end_ms=end,
                needs_review=needs_review,
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
        seen.needs_review = seen.needs_review or point.needs_review
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
