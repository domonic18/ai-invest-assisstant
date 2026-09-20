"""知识库混合检索（arch/12 §7.2）：PG 单库双路召回 + 客户端 RRF 融合。

PG 是唯一存储（无投影层）：词面路走 ``search_text`` 生成列（segment 用
``text`` 列）ILIKE 命中 + pg_trgm ``similarity()`` 排序（GIN 索引）；向量路
走行内 ``embedding halfvec`` 余弦距离（``<=>``，HNSW 索引）。两路 WHERE 与
水合口径同源（published/done/未排除/素材存活/源启用），各类行分别取序后按
分数合并成跨类全局序 → 名次倒数融合（k=60，窗口 50）→ doc_kind 分组截断
水合。

降级语义：embedding 槽位缺失或调用失败退化为词面单路 +
``embedding_unavailable`` 标记；PG 故障随请求异常外溢，不静默降级空结果。
Agent 工具（批次 H）与本服务共用同一入口。
"""

from collections.abc import Callable
from datetime import timedelta
from typing import Any, NamedTuple

import structlog
from sqlalchemy import func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.kb import (
    KbDescribeStatus,
    KbPointStatus,
    KbProcessStatus,
)
from app.constants.pagination import DEFAULT_PAGE, DEFAULT_PAGE_SIZE
from app.core.exceptions import NotFoundError, UnprocessableEntityError
from app.models.kb import KbImageAsset, KbKnowledgePoint, KbMedia, KbSource, KbTranscriptSegment
from app.repositories.kb import point_repository
from app.schemas.kb import (
    KbBrowsePointItem,
    KbChapterNode,
    KbChapterPointsResponse,
    KbPublishedChaptersResponse,
    KbSearchFrameHit,
    KbSearchImageHit,
    KbSearchPointHit,
    KbSearchResponse,
    KbSearchSegmentHit,
)
from app.services.common.minio_service import get_minio_service
from app.services.kb import extract_pipeline as xpipe
from app.services.kb import settings_service
from app.services.kb.embedding_client import KbEmbeddingError, build_embedding_client
from app.services.kb.source_service import get_source

logger = structlog.get_logger(__name__)

_LEX_SIZE = 50
_KNN_K = 20
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
    scope = _Scope(
        source_id=source_id,
        point_type=point_type,
        kind=kind,
        chapter=tuple(chapter) or None,
    )

    degraded: str | None = None
    vector = await _query_vector(session, query)
    if vector is None:
        degraded = "embedding_unavailable"
    rankings = [await _lexical_ranking(session, query, scope)]
    if vector is not None:
        rankings.append(await _vector_ranking(session, vector, scope))

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
        elif doc_kind == "segment" and len(segment_ids) < _SEGMENT_HITS:
            segment_ids.append(db_id)
        elif doc_kind == "image" and len(image_ids) < _IMAGE_HITS:
            image_ids.append(db_id)

    scores = dict(fused)
    points = await _hydrate_points(
        session, point_ids, scores, chapter_prefix=scope.chapter
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


# ---------------------------------------------------------------------------
# 双路召回与 RRF 融合（PG 行内过滤与水合口径同源）
# ---------------------------------------------------------------------------


class _Scope(NamedTuple):
    """检索范围（source/type/kind/章节前缀；两路共用）。"""

    source_id: int | None
    point_type: str | None
    kind: str | None
    chapter: tuple[str, ...] | None


class _LegSpec(NamedTuple):
    """一类检索行的双路声明：doc 前缀 + 行内过滤 + 词面列。"""

    doc_prefix: str
    kind_name: str
    model: Any
    criteria: Callable[[_Scope], list[Any]]
    lex_col: Any


def _escape_like(value: str) -> str:
    """转义 ILIKE 通配符（用户输入按字面匹配，不注入 %/_ 语义）。"""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _point_criteria(scope: _Scope) -> list[Any]:
    """卡片行内过滤：published + 素材存活 + 源启用（口径同 index_service）。"""
    crits: list[Any] = [
        KbKnowledgePoint.status == KbPointStatus.PUBLISHED,
        KbMedia.deleted_at.is_(None),
        KbSource.enabled.is_(True),
        KbSource.deleted_at.is_(None),
    ]
    if scope.source_id is not None:
        crits.append(KbKnowledgePoint.source_id == scope.source_id)
    if scope.point_type is not None:
        crits.append(KbKnowledgePoint.point_type == scope.point_type)
    if scope.chapter is not None:
        crits.append(KbKnowledgePoint.chapter_path.contains(list(scope.chapter)))
    return crits


def _segment_criteria(scope: _Scope) -> list[Any]:
    """分段行内过滤：done 素材存活 + 源启用。"""
    crits: list[Any] = [
        KbMedia.deleted_at.is_(None),
        KbMedia.process_status == KbProcessStatus.DONE,
        KbSource.enabled.is_(True),
        KbSource.deleted_at.is_(None),
    ]
    if scope.source_id is not None:
        crits.append(KbTranscriptSegment.source_id == scope.source_id)
    return crits


def _image_criteria(scope: _Scope) -> list[Any]:
    """图片行内过滤：描述 done + 未排除 + 素材存活 + 源启用。"""
    crits: list[Any] = [
        KbImageAsset.describe_status == KbDescribeStatus.DONE,
        KbImageAsset.index_excluded.is_(False),
        KbMedia.deleted_at.is_(None),
        KbSource.enabled.is_(True),
        KbSource.deleted_at.is_(None),
    ]
    if scope.source_id is not None:
        crits.append(KbImageAsset.source_id == scope.source_id)
    return crits


def _leg_active(leg: _LegSpec, scope: _Scope) -> bool:
    """kind 过滤限定行类；point_type/章节过滤无原始/图片归属，强制只查卡片。"""
    if scope.kind is not None and scope.kind != leg.kind_name:
        return False
    if (scope.point_type is not None or scope.chapter is not None) and (
        leg.kind_name != "point"
    ):
        return False
    return True


async def _lexical_ranking(
    session: AsyncSession, query: str, scope: _Scope
) -> list[str]:
    """词面路：ILIKE 字面命中 + similarity 排序，各类行按分并成全局序。

    词面列：卡片/图片走 ``search_text`` 生成列（未映射 ORM，raw 引用），
    分段直接用 ``text`` 列；均建 pg_trgm GIN 索引。
    """
    pattern = f"%{_escape_like(query)}%"
    scored: list[tuple[float, str]] = []
    for leg in _LEGS:
        if not _leg_active(leg, scope):
            continue
        sim = func.similarity(leg.lex_col, query)
        rows = (
            await session.execute(
                select(leg.model.id, sim.label("sim"))
                .join(KbMedia, leg.model.media_id == KbMedia.id)
                .join(KbSource, leg.model.source_id == KbSource.id)
                .where(*leg.criteria(scope), leg.lex_col.ilike(pattern))
                .order_by(sim.desc())
                .limit(_LEX_SIZE)
            )
        ).all()
        scored.extend((float(sim_v), f"{leg.doc_prefix}-{row_id}") for row_id, sim_v in rows)
    scored.sort(key=lambda item: item[0], reverse=True)
    return [doc_id for _score, doc_id in scored[:_LEX_SIZE]]


async def _vector_ranking(
    session: AsyncSession, vector: list[float], scope: _Scope
) -> list[str]:
    """向量路：halfvec 余弦距离近邻（HNSW），各类行按距离并成全局序。"""
    scored: list[tuple[float, str]] = []
    for leg in _LEGS:
        if not _leg_active(leg, scope):
            continue
        dist = leg.model.embedding.cosine_distance(vector)
        rows = (
            await session.execute(
                select(leg.model.id, dist.label("dist"))
                .join(KbMedia, leg.model.media_id == KbMedia.id)
                .join(KbSource, leg.model.source_id == KbSource.id)
                .where(*leg.criteria(scope), leg.model.embedding.is_not(None))
                .order_by(dist.asc())
                .limit(_KNN_K)
            )
        ).all()
        scored.extend(
            (float(dist_v), f"{leg.doc_prefix}-{row_id}") for row_id, dist_v in rows
        )
    scored.sort(key=lambda item: item[0])
    return [doc_id for _score, doc_id in scored[:_KNN_K]]


async def _query_vector(session: AsyncSession, query: str) -> list[float] | None:
    """查询向量（单条嵌入）；槽位缺失或调用失败返回 None 走词面单路。"""
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
    """``seg-12`` → ("segment", 12)；异形 id 忽略（前缀与 doc 前缀约定一致）。"""
    prefix, _, raw = doc_id.partition("-")
    kind = {"point": "point", "seg": "segment", "img": "image"}.get(prefix)
    if kind is not None and raw.isdigit():
        return kind, int(raw)
    return None


_POINT_LEG = _LegSpec("point", "point", KbKnowledgePoint, _point_criteria,
                      literal_column("search_text"))
_SEGMENT_LEG = _LegSpec("seg", "segment", KbTranscriptSegment, _segment_criteria,
                        KbTranscriptSegment.text)
_IMAGE_LEG = _LegSpec("img", "image", KbImageAsset, _image_criteria,
                      literal_column("search_text"))

_LEGS = (_POINT_LEG, _SEGMENT_LEG, _IMAGE_LEG)


# ---------------------------------------------------------------------------
# PG 水合（卡片全字段以 PG 为真相源，行状态防御过滤兜物化间隙）
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
    chapter_prefix: tuple[str, ...] | None,
) -> list[KbSearchPointHit]:
    """卡片水合：published/章节前缀精筛（WHERE 是 containment 粗筛）+ 案例卡关联帧。"""
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
        if chapter_prefix and tuple(path[: len(chapter_prefix)]) != chapter_prefix:
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
