"""知识库混合检索（arch/12 §7.2）：双路召回 + 客户端 RRF + PG 水合。

ES 8.13 Basic 无原生 RRF retriever（8.16 GA + Enterprise），融合在服务层实现：
BM25（bool match，size=50）与 knn（顶层 k=20/candidates=200）两次查询 →
按名次倒数融合（k=60，窗口 50，只看排名不做分数归一化）→ doc_kind 分组
→ PG 回表水合（ES 仅存投影，卡片全字段以 PG 为真相源）。

降级语义（检索面故障不外溢）：ES 不可用返回空结果 + ``es_unavailable`` 标记；
embedding 槽位缺失或调用失败退化为 BM25 单路 + ``embedding_unavailable`` 标记。
Agent 工具（批次 H）与本服务共用同一入口。
"""

from datetime import timedelta
from typing import Any

import structlog
from elasticsearch import AsyncElasticsearch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.kb import (
    KB_INDEX_ALIAS,
    KbDescribeStatus,
    KbPointStatus,
)
from app.core.config import get_settings
from app.core.exceptions import NotFoundError, UnprocessableEntityError
from app.models.kb import KbImageAsset, KbKnowledgePoint, KbMedia, KbTranscriptSegment
from app.schemas.kb import (
    KbChapterNode,
    KbPublishedChaptersResponse,
    KbSearchFrameHit,
    KbSearchImageHit,
    KbSearchPointHit,
    KbSearchResponse,
    KbSearchSegmentHit,
)
from app.services.common.minio_service import get_minio_service
from app.services.kb import settings_service
from app.services.kb.embedding_client import KbEmbeddingError, build_embedding_client
from app.services.kb.source_service import get_source

logger = structlog.get_logger(__name__)

_BM25_SIZE = 50
_KNN_K = 20
_KNN_CANDIDATES = 200
_RRF_K = 60
_FUSED_WINDOW = 50
_SEGMENT_HITS = 10
_IMAGE_HITS = 12
#: 课程命中起播前滚（需求 3~5s 口径取下限）
_SEEK_REWIND_MS = 4000
#: 案例卡片关联帧：命中区间外扩秒数与取帧上限
_CASE_FRAME_PAD_MS = 20_000
_CASE_FRAME_LIMIT = 3
_THUMB_URL_TTL = timedelta(hours=1)
_QUERY_EMBED_TIMEOUT = 10.0


async def search(
    session: AsyncSession,
    *,
    q: str,
    source_id: int | None = None,
    chapter_path: list[str] | None = None,
    point_type: str | None = None,
    kind: str | None = None,
) -> KbSearchResponse:
    """混合检索：RRF 融合后按 doc_kind 分组水合（三类命中独立列表）。

    chapter_path 前缀过滤只作用于知识卡片（章节归属仅卡片携带），过滤时
    原文/图片命中不返回。
    """
    query = q.strip()
    if not query:
        return KbSearchResponse(query=q)
    chapter = [seg.strip() for seg in chapter_path or [] if seg.strip()]
    settings = await settings_service.get_settings_row(session)
    point_cap = max(1, settings.top_k or 8)
    filters = _es_filters(source_id=source_id, point_type=point_type, kind=kind)

    rankings: list[list[str]] = []
    degraded: str | None = None
    es = AsyncElasticsearch(get_settings().elasticsearch_url)
    try:
        rankings.append(await _bm25_ranking(es, query, filters))
        vector = await _query_vector(session, query)
        if vector is None:
            degraded = "embedding_unavailable"
        else:
            rankings.append(await _knn_ranking(es, vector, filters))
    except Exception as exc:  # noqa: BLE001 —— 检索面降级不外溢
        logger.warning("kb_search_es_unavailable", error=str(exc)[:200])
        return KbSearchResponse(query=q, degraded="es_unavailable")
    finally:
        await es.close()

    fused = _rrf_fuse(rankings)
    point_ids: list[int] = []
    segment_ids: list[int] = []
    image_ids: list[int] = []
    for doc_id, _score in fused:
        parsed = _doc_key(doc_id)
        if parsed is None:
            continue
        doc_kind, db_id = parsed
        if doc_kind == "point":
            if len(point_ids) < point_cap:
                point_ids.append(db_id)
        elif chapter:
            continue  # 章节过滤时原文/图片无章节归属，不返回
        elif doc_kind == "segment" and len(segment_ids) < _SEGMENT_HITS:
            segment_ids.append(db_id)
        elif doc_kind == "image" and len(image_ids) < _IMAGE_HITS:
            image_ids.append(db_id)

    scores = dict(fused)
    points = await _hydrate_points(
        session, point_ids, scores, chapter_prefix=chapter or None
    )
    segments = (
        await _hydrate_segments(session, segment_ids, scores) if segment_ids else []
    )
    images = await _hydrate_images(session, image_ids, scores) if image_ids else []
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


# ---------------------------------------------------------------------------
# 双路召回与 RRF 融合
# ---------------------------------------------------------------------------


def _es_filters(
    *, source_id: int | None, point_type: str | None, kind: str | None
) -> list[dict[str, Any]]:
    """过滤器全链路透传（BM25 filter 与 knn filter 同构）。"""
    filters: list[dict[str, Any]] = []
    if kind is not None:
        filters.append({"term": {"doc_kind": kind}})
    if source_id is not None:
        filters.append({"term": {"source_id": source_id}})
    if point_type is not None:
        # 分段/图片文档 point_type 为 null，term 不命中即自然排除
        filters.append({"term": {"point_type": point_type}})
    return filters


async def _bm25_ranking(
    es: AsyncElasticsearch, query: str, filters: list[dict[str, Any]]
) -> list[str]:
    resp = await es.search(
        index=KB_INDEX_ALIAS,
        body={
            "size": _BM25_SIZE,
            "query": {
                "bool": {
                    "must": [{"match": {"text": {"query": query}}}],
                    "filter": filters,
                }
            },
            "_source": False,
        },
    )
    return [hit["_id"] for hit in resp["hits"]["hits"]]


async def _knn_ranking(
    es: AsyncElasticsearch, vector: list[float], filters: list[dict[str, Any]]
) -> list[str]:
    resp = await es.search(
        index=KB_INDEX_ALIAS,
        body={
            "knn": {
                "field": "embedding",
                "query_vector": vector,
                "k": _KNN_K,
                "num_candidates": _KNN_CANDIDATES,
                "filter": {"bool": {"filter": filters}},
            },
            "size": _KNN_K,
            "_source": False,
        },
    )
    return [hit["_id"] for hit in resp["hits"]["hits"]]


async def _query_vector(session: AsyncSession, query: str) -> list[float] | None:
    """查询向量（单条嵌入）；槽位缺失或调用失败返回 None 走 BM25 单路。"""
    try:
        embed = await build_embedding_client(session)
        vectors = await embed.embed(
            [query],
            detail={"purpose": "kb_search"},
            timeout=_QUERY_EMBED_TIMEOUT,
        )
    except (UnprocessableEntityError, KbEmbeddingError) as exc:
        logger.warning("kb_search_embedding_unavailable", error=str(exc)[:200])
        return None
    return vectors[0] if vectors else None


def _rrf_fuse(rankings: list[list[str]]) -> list[tuple[str, float]]:
    """客户端 RRF：score = Σ 1/(k + rank)，同名次文档两路叠加。"""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (_RRF_K + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)[
        :_FUSED_WINDOW
    ]


def _doc_key(doc_id: str) -> tuple[str, int] | None:
    """``seg-12`` → ("segment", 12)；异形 id 忽略（前缀与索引文档 id 约定一致）。"""
    prefix, _, raw = doc_id.partition("-")
    kind = {"point": "point", "seg": "segment", "img": "image"}.get(prefix)
    if kind is not None and raw.isdigit():
        return kind, int(raw)
    return None


# ---------------------------------------------------------------------------
# PG 水合（ES 只回 id，卡片全字段以 PG 为真相源）
# ---------------------------------------------------------------------------


async def _media_map(session: AsyncSession, media_ids: set[int]) -> dict[int, KbMedia]:
    if not media_ids:
        return {}
    rows = (
        await session.execute(select(KbMedia).where(KbMedia.id.in_(media_ids)))
    ).scalars().all()
    return {row.id: row for row in rows if row.deleted_at is None}


async def _hydrate_points(
    session: AsyncSession,
    ids: list[int],
    scores: dict[str, float],
    *,
    chapter_prefix: list[str] | None,
) -> list[KbSearchPointHit]:
    """卡片水合：published 防御过滤 + 章节前缀过滤 + 案例卡关联帧。"""
    rows = (
        await session.execute(select(KbKnowledgePoint).where(KbKnowledgePoint.id.in_(ids)))
    ).scalars().all()
    by_id = {row.id: row for row in rows}
    medias = await _media_map(
        session, {row.media_id for row in rows if row.status == KbPointStatus.PUBLISHED}
    )
    hits: list[KbSearchPointHit] = []
    for db_id in ids:
        row = by_id.get(db_id)
        if row is None or row.status != KbPointStatus.PUBLISHED:
            continue
        path = [str(p) for p in row.chapter_path or []]
        if chapter_prefix and path[: len(chapter_prefix)] != chapter_prefix:
            continue
        media = medias.get(row.media_id)
        if media is None:
            continue
        frames = (
            await _case_frames(session, media, row)
            if media.media_kind != "book" and row.point_type == "case"
            else []
        )
        hits.append(
            KbSearchPointHit(
                id=row.id,
                source_id=row.source_id,
                media_id=row.media_id,
                media_kind=media.media_kind,
                episode_no=media.episode_no,
                media_title=media.title,
                point_type=row.point_type,
                title=row.title,
                body=row.body,
                term_definition=row.term_definition,
                applicable_scene=row.applicable_scene,
                excerpt=row.excerpt,
                chapter_path=path,
                related_ids=[int(r) for r in row.related_ids or []],
                start_ms=row.start_ms,
                end_ms=row.end_ms,
                page_start=row.page_start,
                page_end=row.page_end,
                score=scores.get(f"point-{row.id}", 0.0),
                frames=frames,
            )
        )
    return hits


async def _case_frames(
    session: AsyncSession, media: KbMedia, point: KbKnowledgePoint
) -> list[KbSearchFrameHit]:
    """案例卡关联帧：命中时间窗外扩取帧（缩略图短时效签名）。"""
    if point.start_ms is None:
        return []
    window_end = point.end_ms if point.end_ms is not None else point.start_ms
    rows = (
        await session.execute(
            select(KbImageAsset)
            .where(
                KbImageAsset.media_id == media.id,
                KbImageAsset.describe_status == KbDescribeStatus.DONE,
                KbImageAsset.index_excluded.is_(False),
                KbImageAsset.start_ms >= point.start_ms - _CASE_FRAME_PAD_MS,
                KbImageAsset.start_ms <= window_end + _CASE_FRAME_PAD_MS,
            )
            .order_by(KbImageAsset.start_ms)
            .limit(_CASE_FRAME_LIMIT)
        )
    ).scalars().all()
    if not rows:
        return []
    minio = get_minio_service()
    hits = []
    for row in rows:
        hits.append(
            KbSearchFrameHit(
                id=row.id,
                start_ms=row.start_ms,
                thumb_url=await minio.get_presigned_url(
                    row.thumb_cos_key or row.cos_key, expires=_THUMB_URL_TTL
                ),
                caption=row.caption,
            )
        )
    return hits


async def _hydrate_segments(
    session: AsyncSession, ids: list[int], scores: dict[str, float]
) -> list[KbSearchSegmentHit]:
    """原文分段水合：附前滚后起播点 seekMs。"""
    rows = (
        await session.execute(
            select(KbTranscriptSegment).where(KbTranscriptSegment.id.in_(ids))
        )
    ).scalars().all()
    by_id = {row.id: row for row in rows}
    medias = await _media_map(session, {row.media_id for row in rows})
    hits: list[KbSearchSegmentHit] = []
    for db_id in ids:
        row = by_id.get(db_id)
        if row is None:
            continue
        media = medias.get(row.media_id)
        if media is None:
            continue
        hits.append(
            KbSearchSegmentHit(
                id=row.id,
                source_id=row.source_id,
                media_id=row.media_id,
                media_kind=media.media_kind,
                episode_no=media.episode_no,
                media_title=media.title,
                text=row.text,
                start_ms=row.start_ms,
                end_ms=row.end_ms,
                seek_ms=(
                    max(0, row.start_ms - _SEEK_REWIND_MS)
                    if row.start_ms is not None
                    else None
                ),
                score=scores.get(f"seg-{row.id}", 0.0),
            )
        )
    return hits


async def _hydrate_images(
    session: AsyncSession, ids: list[int], scores: dict[str, float]
) -> list[KbSearchImageHit]:
    """图片命中水合（done 未排除防御过滤，缩略图短时效签名）。"""
    rows = (
        await session.execute(select(KbImageAsset).where(KbImageAsset.id.in_(ids)))
    ).scalars().all()
    by_id = {
        row.id: row
        for row in rows
        if row.describe_status == KbDescribeStatus.DONE and not row.index_excluded
    }
    medias = await _media_map(session, {row.media_id for row in by_id.values()})
    minio = get_minio_service()
    hits: list[KbSearchImageHit] = []
    for db_id in ids:
        row = by_id.get(db_id)
        if row is None:
            continue
        media = medias.get(row.media_id)
        if media is None:
            continue
        hits.append(
            KbSearchImageHit(
                id=row.id,
                source_id=row.source_id,
                media_id=row.media_id,
                media_kind=media.media_kind,
                episode_no=media.episode_no,
                page_no=row.page_no,
                start_ms=row.start_ms,
                text_in_image=row.text_in_image,
                caption=row.caption,
                thumb_url=await minio.get_presigned_url(
                    row.thumb_cos_key or row.cos_key, expires=_THUMB_URL_TTL
                ),
                score=scores.get(f"img-{row.id}", 0.0),
            )
        )
    return hits
