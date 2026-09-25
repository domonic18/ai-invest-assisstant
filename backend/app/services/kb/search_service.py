"""知识库混合检索（arch/09 §7.2）：PG 单库双路召回 + 客户端 RRF 融合。

入口编排层：范围组装 → ``search_ranking`` 双路召回与 RRF 融合 → doc_kind
分桶截断 → ``search_hydrate`` 分组水合。PG 是唯一存储（无投影层），两路
WHERE 与水合口径同源。降级语义：embedding 槽位缺失或调用失败退化为词面
单路 + ``embedding_unavailable`` 标记；PG 故障随请求异常外溢，不静默降级
空结果。Agent 工具（批次 H）与本服务共用同一入口。
"""

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.pagination import DEFAULT_PAGE, DEFAULT_PAGE_SIZE
from app.core.exceptions import NotFoundError, UnprocessableEntityError
from app.repositories.kb import point_repository
from app.schemas.kb import (
    KbBrowsePointItem,
    KbChapterNode,
    KbChapterPointsResponse,
    KbPublishedChaptersResponse,
    KbSearchResponse,
)
from app.services.kb import extract_pipeline as xpipe
from app.services.kb import search_hydrate, search_ranking, settings_service
from app.services.kb.source_service import get_source

_SEGMENT_HITS = 10
_IMAGE_HITS = 12

logger = structlog.get_logger(__name__)


async def search(
    session: AsyncSession,
    *,
    q: str,
    source_id: int | None = None,
    chapter_path: list[str] | None = None,
    point_type: str | None = None,
    kind: str | None = None,
) -> KbSearchResponse:
    """混合检索：双路全局序 RRF 融合后按 doc_kind 分组水合。

    chapter_path 前缀过滤进两路行内 WHERE（JSONB containment 粗筛 + 水合层
    前缀精筛），并强制只召回卡片（原文/图片无章节归属）。
    """
    query = q.strip()
    if not query:
        return KbSearchResponse(query=q)
    chapter = [seg.strip() for seg in chapter_path or [] if seg.strip()]
    settings = await settings_service.get_settings_row(session)
    point_cap = max(1, settings.top_k or 8)
    scope = search_ranking._Scope(
        source_id=source_id,
        point_type=point_type,
        kind=kind,
        chapter=tuple(chapter) or None,
    )

    degraded: str | None = None
    vector = await search_ranking._query_vector(session, query)
    if vector is None:
        degraded = "embedding_unavailable"
    rankings = [await search_ranking._lexical_ranking(session, query, scope)]
    if vector is not None:
        rankings.append(await search_ranking._vector_ranking(session, vector, scope))

    fused = search_ranking._rrf_fuse(rankings)
    point_ids: list[int] = []
    segment_ids: list[int] = []
    image_ids: list[int] = []
    for doc_id, _score in fused:
        parsed = search_ranking._doc_key(doc_id)
        if parsed is None:
            continue
        doc_kind, db_id = parsed
        if doc_kind == "point":
            if len(point_ids) < point_cap:
                point_ids.append(db_id)
        elif doc_kind == "segment" and len(segment_ids) < _SEGMENT_HITS:
            segment_ids.append(db_id)
        elif doc_kind == "image" and len(image_ids) < _IMAGE_HITS:
            image_ids.append(db_id)

    scores = dict(fused)
    points = await search_hydrate._hydrate_points(
        session, point_ids, scores, chapter_prefix=scope.chapter
    )
    segments = (
        await search_hydrate._hydrate_segments(session, segment_ids, scores)
        if segment_ids
        else []
    )
    images = (
        await search_hydrate._hydrate_images(session, image_ids, scores)
        if image_ids
        else []
    )
    logger.info(
        "kb_search_executed",
        q=query,
        source_id=source_id,
        chapter_path=chapter,
        point_type=point_type,
        kind=kind,
        points=len(points),
        segments=len(segments),
        images=len(images),
        degraded=degraded,
    )
    return KbSearchResponse(
        query=q,
        degraded=degraded,
        points=points,
        segments=segments,
        images=images,
    )


async def get_published_chapters(
    session: AsyncSession, source_id: int
) -> KbPublishedChaptersResponse:
    """发布态目录树（消费侧导航；停用知识库不暴露）。"""
    source = await get_source(session, source_id)
    if not source.enabled:
        raise NotFoundError(f"知识库 {source_id} 未启用")
    tree = source.chapter_tree or {}
    return KbPublishedChaptersResponse(
        chapters=_to_nodes(tree.get("published")),
    )


def _to_nodes(raw: Any) -> list[KbChapterNode]:
    nodes: list[KbChapterNode] = []
    for item in raw or []:
        node = KbChapterNode(
            id=str(item.get("id", "")),
            title=str(item.get("title", "")),
            children=_to_nodes(item.get("children")),
        )
        nodes.append(node)
    return nodes


async def list_chapter_points(
    session: AsyncSession,
    source_id: int,
    *,
    chapter_path: list[str],
    page: int = DEFAULT_PAGE,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> KbChapterPointsResponse:
    """章节卡片清单（浏览路径）：确定性排序分页，读 PG 真相源。

    与 ``search`` 的分工：搜索按相关性截断 top-k，浏览要全集 + 稳定顺序
    （episode_no/start_ms/page_start）+ 分页；章节 id 对发布树校验，未知
    章节 422（浏览语义可区分「空章节」与「打错 id」，搜索语义则静默空）。
    """
    source = await get_source(session, source_id)
    if not source.enabled:
        raise NotFoundError(f"知识库 {source_id} 未启用")
    if not chapter_path:
        raise UnprocessableEntityError("chapter_path 不能为空")
    published = (source.chapter_tree or {}).get("published")
    if tuple(chapter_path) not in xpipe.chapter_id_paths(published):
        raise UnprocessableEntityError(
            f"章节 {'/'.join(chapter_path)} 不在发布目录树中"
        )
    offset = (page - 1) * page_size
    total = await point_repository.count_published_by_chapter(
        session, source_id, chapter_path
    )
    rows = (
        await point_repository.list_published_by_chapter(
            session, source_id, chapter_path, offset=offset, limit=page_size
        )
        if total
        else []
    )
    return KbChapterPointsResponse(
        total=total,
        page=page,
        page_size=page_size,
        points=[
            KbBrowsePointItem(
                id=p.id,
                source_id=p.source_id,
                media_id=p.media_id,
                media_kind=media_kind,
                episode_no=episode_no,
                media_title=media_title,
                point_type=p.point_type,
                title=p.title,
                body=p.body,
                term_definition=p.term_definition,
                applicable_scene=p.applicable_scene,
                excerpt=p.excerpt,
                chapter_path=[str(c) for c in p.chapter_path or []],
                related_ids=[int(r) for r in p.related_ids or []],
                start_ms=p.start_ms,
                end_ms=p.end_ms,
                page_start=p.page_start,
                page_end=p.page_end,
            )
            for p, episode_no, media_title, media_kind in rows
        ],
    )
