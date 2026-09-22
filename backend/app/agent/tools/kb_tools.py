"""知识库消费工具（批次 H1）：Agent 会话内检索投资课程知识卡片。

全员注入助手会话（与消费页共用 ``search_service.search`` 单一入口），
返回压缩卡片集（受 top_k 约束），引用带集数/时间码/章节/页码可溯源；
``media`` 引用（素材 id/类型/起播点/页码）仅在用户想看课程讲解原片时
按 ``include_media=True`` 返回，前端据此渲染可点击 chip 跳转播放——
播放凭证走 playback-token 白名单校验。
"""

from typing import Any

from langchain_core.tools import tool
from sqlalchemy import select

from app.constants.kb import KbPointType
from app.core.database import AsyncSessionLocal
from app.models.kb import KbSource
from app.services.kb import search_service

POINT_TYPE_LABELS: dict[str, str] = {
    KbPointType.CONCEPT.value: "概念",
    KbPointType.THEOREM.value: "定理",
    KbPointType.METHOD.value: "方法",
    KbPointType.DISCIPLINE.value: "纪律",
    KbPointType.CASE.value: "案例",
}

_BODY_MAX = 500
_DEFINITION_MAX = 200
_EXCERPT_MAX = 200
_SEGMENT_MAX = 3
_SEGMENT_TEXT_MAX = 200


def _timecode(start_ms: int | None, end_ms: int | None) -> str | None:
    """毫秒 → ``MM:SS`` / ``H:MM:SS`` 时间码（缺端点只出一端）。"""

    def fmt(ms: int) -> str:
        total = ms // 1000
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

    if start_ms is None and end_ms is None:
        return None
    if end_ms is None:
        return fmt(start_ms or 0)
    if start_ms is None:
        return fmt(end_ms)
    return f"{fmt(start_ms)}-{fmt(end_ms)}"


def _clip(text: str | None, limit: int) -> str | None:
    if not text:
        return None
    return text if len(text) <= limit else text[:limit] + "…"


def _media_ref(hit: Any) -> dict[str, Any] | None:
    """结构化媒体引用：课程带 seek 起播点，书带页码；无法定位返回 None。"""
    if hit.media_kind == "book":
        page_no = getattr(hit, "page_start", None)
        if page_no is None:
            return None
        ref: dict[str, Any] = {"id": hit.media_id, "kind": hit.media_kind, "page_no": page_no}
    else:
        seek_ms = getattr(hit, "seek_ms", None)
        if seek_ms is None:
            seek_ms = hit.start_ms
        if seek_ms is None:
            return None
        ref = {"id": hit.media_id, "kind": hit.media_kind, "seek_ms": seek_ms}
    if hit.media_title:
        ref["title"] = hit.media_title
    if hit.episode_no is not None:
        ref["episode_no"] = hit.episode_no
    return ref


def _locate(
    source_name: str,
    media_title: str | None,
    episode_no: int | None,
    media_kind: str,
    timecode: str | None,
    chapter_path: list[str],
    page_start: int | None,
    page_end: int | None,
) -> str:
    """引用定位串：课程带集数与时间码，书带页码，章节路径前缀。"""
    if media_kind == "book":
        where = f"《{media_title or source_name}》"
        if page_start is not None:
            pages = str(page_start) if page_end == page_start or page_end is None else f"{page_start}-{page_end}"
            where += f" 第{pages}页"
    else:
        where = f"《{source_name}》"
        if episode_no is not None:
            where += f" 第{episode_no}集"
        elif media_title:
            where += f"「{media_title}」"
        if timecode:
            where += f" {timecode}"
    if chapter_path:
        where += f"（{'/'.join(chapter_path)}）"
    return where


@tool
async def search_knowledge_base(
    query: str,
    source: str | None = None,
    chapter: str | None = None,
    point_type: str | None = None,
    include_media: bool = False,
) -> dict[str, Any]:
    """检索投资课程知识库（已审核发布的知识卡片）。分析个股/大盘/板块走势、
    判断技术形态、讨论买卖点时应主动检索相关方法论（形态识别/量价关系/趋势纪律）
    佐证分析结论；用户直接询问知识概念时也须检索。

    Args:
        query: 检索语句，如 "均线金叉的买入纪律" 或 "缠论中枢"。
        source: 知识库名称过滤（管理台登记的名称）；不传搜全部知识库。
        chapter: 章节路径过滤，层级用 / 连接，如 "第二讲/均线系统"。
        point_type: 卡片类型过滤：concept（概念）/ theorem（定理）/ method（方法）/ discipline（纪律）/ case（案例）。
        include_media: 是否附带媒体定位（视频起播点/书籍页码，前端据此渲染
            播放按钮）。仅当用户想学习知识点的课程讲解、或明确要求看视频
            原片/书籍原文时传 true；在分析任务中引用方法论佐证时保持 false。
    """
    if point_type is not None and point_type not in POINT_TYPE_LABELS:
        return {
            "error": (
                f"point_type 须为 {'/'.join(POINT_TYPE_LABELS)} 之一，当前值：{point_type}"
            )
        }
    chapter_path = [seg.strip() for seg in (chapter or "").split("/") if seg.strip()]
    async with AsyncSessionLocal() as session:
        source_id: int | None = None
        source_name = "全部知识库"
        if source is not None:
            row = (
                await session.execute(
                    select(KbSource.id, KbSource.name)
                    .where(
                        KbSource.name == source,
                        KbSource.deleted_at.is_(None),
                        KbSource.enabled.is_(True),
                    )
                    .limit(1)
                )
            ).first()
            if row is None:
                available = (
                    await session.execute(
                        select(KbSource.name)
                        .where(KbSource.deleted_at.is_(None), KbSource.enabled.is_(True))
                        .order_by(KbSource.id.asc())
                    )
                ).scalars().all()
                listing = "、".join(available) if available else "（当前无启用的知识库）"
                return {"error": f"未找到启用的知识库「{source}」，可用：{listing}"}
            source_id, source_name = row.id, row.name

        result = await search_service.search(
            session,
            q=query,
            source_id=source_id,
            chapter_path=chapter_path or None,
            point_type=point_type,
        )
        source_names: dict[int, str] = {}
        if source_id is None:
            hit_source_ids = {h.source_id for h in result.points} | {
                h.source_id for h in result.segments
            }
            if hit_source_ids:
                rows = (
                    await session.execute(
                        select(KbSource.id, KbSource.name).where(
                            KbSource.id.in_(hit_source_ids)
                        )
                    )
                ).all()
                source_names = {int(row_id): name for row_id, name in rows}

    def hit_source(hit: Any) -> str:
        return source_names.get(hit.source_id, hit.media_title or "")

    points: list[dict[str, Any]] = []
    for hit in result.points:
        card: dict[str, Any] = {
            "type": POINT_TYPE_LABELS.get(hit.point_type, hit.point_type),
            "title": hit.title,
            "citation": _locate(
                source_name if source_id is not None else hit_source(hit),
                hit.media_title,
                hit.episode_no,
                hit.media_kind,
                _timecode(hit.start_ms, hit.end_ms),
                hit.chapter_path,
                hit.page_start,
                hit.page_end,
            ),
        }
        if body := _clip(hit.body, _BODY_MAX):
            card["body"] = body
        if definition := _clip(hit.term_definition, _DEFINITION_MAX):
            card["term_definition"] = definition
        if excerpt := _clip(hit.excerpt, _EXCERPT_MAX):
            card["excerpt"] = excerpt
        if include_media and (ref := _media_ref(hit)):
            card["media"] = ref
        points.append(card)

    segments: list[dict[str, Any]] = []
    for seg in result.segments[:_SEGMENT_MAX]:
        segments.append(
            {
                "citation": _locate(
                    source_name if source_id is not None else hit_source(seg),
                    seg.media_title,
                    seg.episode_no,
                    seg.media_kind,
                    _timecode(seg.start_ms, seg.end_ms),
                    [],
                    None,
                    None,
                ),
                "text": _clip(seg.text, _SEGMENT_TEXT_MAX),
            }
        )
        if include_media and (ref := _media_ref(seg)):
            segments[-1]["media"] = ref

    payload: dict[str, Any] = {
        "query": query,
        "source": source_name,
        "points": points,
        "segments": segments,
    }
    if result.degraded is not None:
        payload["note"] = (
            "注意：向量检索当前不可用，本次仅词面匹配，长自然语言查询召回可能不全。"
        )
    elif not points and not segments:
        payload["note"] = "无命中卡片。可尝试更换关键词、放宽 source/chapter/point_type 过滤。"
    return payload
