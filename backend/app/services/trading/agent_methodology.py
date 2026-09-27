"""交易 Agent 方法论基座装配（方案 A：KB 直读双层注入，2026-09-26 定版）。

温程《趋势理论》整套方法论以 KB 为单一真相源（``kb_knowledge_point``，
不复制进 agent_memory），三层注入每日计划 prompt：
- 纪律层：``point_type='discipline'`` 全量条目（硬约束，不参与检索）；
- 总纲层：发布目录树扁平化为体系骨架（保证体系级认知每日在场）；
- 方法层：当日盘面文本（复盘解读 + 涨停归因 + 异动）作为 query，按
  method/theorem/concept/case 四类各做一次混合检索（halfvec+trgm RRF），
  去重合并截断。

agent_memory 只装迭代经验（复盘沉淀 + 手动沉淀），与基座分离；经验可修正
方法应用，但不得违反纪律硬约束。降级语义：``methodology_source_id`` 未
配置或知识源缺失/停用时返回 None（计划照常生成、仅无基座，warning 记录）；
真实查询异常向上传播，交由定时任务退避重试。
"""

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.kb import KbPointStatus
from app.models.kb import KbKnowledgePoint, KbMedia, KbSource
from app.services.kb import search_service

logger = structlog.get_logger(__name__)

#: 方法层检索注入条数上限（四类合并去重后）
_RELEVANT_TOP_N = 40
#: 方法层参与检索的知识卡片类型（discipline 全量注入，不参与检索）
_RETRIEVAL_POINT_TYPES = ("method", "theorem", "concept", "case")
#: 检索 query 最大长度（embedding 模型 token 上限保护）
_QUERY_MAX_CHARS = 1200


async def build_methodology_input(
    session: AsyncSession, *, source_id: int | None, query_text: str | None
) -> dict[str, Any] | None:
    """装配方法论基座输入（调用方传注册行 ``methodology_source_id``；
    未配置/知识源不可用时 None，计划生成照常进行）。"""
    if source_id is None:
        return None
    source = await session.get(KbSource, source_id)
    if source is None or not source.enabled:
        logger.warning(
            "agent_methodology_source_unavailable",
            source_id=source_id,
            enabled=getattr(source, "enabled", None),
        )
        return None
    disciplines = await _list_disciplines(session, source_id)
    relevant = await _retrieve_relevant(session, source_id, query_text)
    return {
        "source_id": source_id,
        "outline": _flatten_outline((source.chapter_tree or {}).get("published")),
        "disciplines": disciplines,
        "relevant": relevant,
    }


def build_retrieval_query(
    review: Any, attribution: Any, anomalies: Any
) -> str | None:
    """从当日盘面输入提取检索 query（复盘解读 + 涨停归因 + 异动的字符串拼接）。"""
    parts: list[str] = []

    def _collect(value: Any) -> None:
        if isinstance(value, str):
            text = value.strip()
            if text:
                parts.append(text)
        elif isinstance(value, dict):
            for item in value.values():
                _collect(item)
        elif isinstance(value, list):
            for item in value:
                _collect(item)

    _collect(review)
    _collect(attribution)
    _collect(anomalies)
    return " ".join(parts)[:_QUERY_MAX_CHARS] or None


async def build_methodology_view(
    session: AsyncSession, *, source_id: int | None
) -> dict[str, Any] | None:
    """方法论基座可视化载荷（配置页只读浏览，D30）。

    章节大纲 + 纪律全量 + 方法/定理/概念/案例全量（不做检索裁剪）。
    未绑定或知识源缺失/停用时 None（与注入降级语义一致）。
    """
    if source_id is None:
        return None
    source = await session.get(KbSource, source_id)
    if source is None or not source.enabled:
        return None
    return {
        "source_id": source_id,
        "source_name": source.name,
        "outline": _flatten_outline((source.chapter_tree or {}).get("published")),
        "disciplines": await _list_disciplines(session, source_id),
        "points": await _list_points(session, source_id, _RETRIEVAL_POINT_TYPES),
    }


async def _list_points(
    session: AsyncSession, source_id: int, point_types: tuple[str, ...]
) -> list[dict[str, Any]]:
    """指定类型 published 全量条目（可视化层用，与检索无关）。"""
    rows = await session.execute(
        select(KbKnowledgePoint.point_type, KbKnowledgePoint.title, KbKnowledgePoint.body)
        .join(KbMedia, KbKnowledgePoint.media_id == KbMedia.id)
        .where(
            KbKnowledgePoint.source_id == source_id,
            KbKnowledgePoint.status == KbPointStatus.PUBLISHED,
            KbKnowledgePoint.point_type.in_(point_types),
            KbMedia.deleted_at.is_(None),
        )
        .order_by(KbKnowledgePoint.point_type.asc(), KbKnowledgePoint.id.asc())
    )
    return [
        {"point_type": row.point_type, "title": row.title, "body": row.body}
        for row in rows.all()
    ]


async def _list_disciplines(
    session: AsyncSession, source_id: int
) -> list[dict[str, Any]]:
    """纪律层全量条目（published，硬约束每日全量注入，不参与检索）。"""
    rows = await session.execute(
        select(KbKnowledgePoint.id, KbKnowledgePoint.title, KbKnowledgePoint.body)
        .join(KbMedia, KbKnowledgePoint.media_id == KbMedia.id)
        .where(
            KbKnowledgePoint.source_id == source_id,
            KbKnowledgePoint.status == KbPointStatus.PUBLISHED,
            KbKnowledgePoint.point_type == "discipline",
            KbMedia.deleted_at.is_(None),
        )
        .order_by(KbKnowledgePoint.id.asc())
    )
    return [
        {"id": row.id, "title": row.title, "body": row.body} for row in rows.all()
    ]


async def _retrieve_relevant(
    session: AsyncSession, source_id: int, query_text: str | None
) -> list[dict[str, Any]]:
    """方法层按当日盘面检索（四类各一次混合检索，去重合并截断；query 空则跳过）。"""
    query = (query_text or "").strip()
    if not query:
        return []
    seen: set[int] = set()
    items: list[dict[str, Any]] = []
    for point_type in _RETRIEVAL_POINT_TYPES:
        response = await search_service.search(
            session, q=query, source_id=source_id, point_type=point_type
        )
        for hit in response.points:
            if hit.id in seen:
                continue
            seen.add(hit.id)
            items.append(
                {
                    "id": hit.id,
                    "point_type": hit.point_type,
                    "title": hit.title,
                    "body": hit.body,
                }
            )
            if len(items) >= _RELEVANT_TOP_N:
                return items
    return items


def _flatten_outline(nodes: Any) -> str:
    """发布目录树 → 缩进大纲文本（体系总纲；空树返回空串）。"""
    lines: list[str] = []

    def _walk(items: Any, depth: int) -> None:
        for item in items or []:
            title = str(item.get("title", "")).strip()
            if title:
                lines.append(f"{'  ' * depth}- {title}")
            _walk(item.get("children"), depth + 1)

    _walk(nodes, 0)
    return "\n".join(lines)
