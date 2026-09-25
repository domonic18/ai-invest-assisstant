"""检索双路召回与 RRF 融合（arch/09 §7.2 下半）。

词面路走 ``search_text`` 生成列 ILIKE 命中 + pg_trgm ``similarity()`` 排序
（GIN 索引），向量路走行内 ``embedding halfvec`` 余弦距离（``<=>``，HNSW
索引）；两路 WHERE 与水合口径同源（published/done/未排除/素材存活/源启用），
各类行分别取序后按分数合并成跨类全局序 → 名次倒数融合（k=60，窗口 50）。
入口编排见 ``search_service``。
"""

from collections.abc import Callable
from typing import Any, NamedTuple

import structlog
from sqlalchemy import func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.kb import (
    KbDescribeStatus,
    KbPointStatus,
    KbProcessStatus,
)
from app.core.exceptions import UnprocessableEntityError
from app.models.kb import (
    KbImageAsset,
    KbKnowledgePoint,
    KbMedia,
    KbSource,
    KbTranscriptSegment,
)
from app.services.kb.embedding_client import KbEmbeddingError, build_embedding_client

logger = structlog.get_logger(__name__)

_LEX_SIZE = 50
_KNN_K = 20
_RRF_K = 60
_FUSED_WINDOW = 50
_QUERY_EMBED_TIMEOUT = 10.0


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
