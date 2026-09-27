"""知识库嵌入物化服务（kb-index internal 任务的执行体，arch/09 §7.1）。

PG 是唯一存储，检索面同库内嵌（无投影层）：本服务把三类 ``embedding_dirty``
行的检索文本（point/image 按各自拼接口径、segment 用 ``text``，与
``search_text`` 生成列同式）批量嵌入并写回行内 ``embedding halfvec`` 列，
写入与清脏同事务。

- **增量**（默认，*/5 cron）：单轮各类限量一批，余量下轮续跑；不可见行
  （rejected/未发布点、排除图片、软删/未 done 素材、停用源）向量置 NULL——
  检索可见性由行状态与检索过滤共同保证，无投影同步与 tombstone；
- **全量重嵌**（``force_rebuild``，后台手动触发或模型切换）：三表全量置脏后
  单轮清完，行级覆写不中断检索；
- **维度护栏**：embedding 槽位实测维度 ≠ 列定义（``halfvec(2048)``）时
  SKIPPED 显式报错——换维度需先执行列类型迁移 + 索引重建再全量重嵌。
"""

from collections.abc import Callable
from typing import Any, NamedTuple

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.kb import (
    KB_EMBEDDING_DIMS,
    KB_INDEX_BATCH_SIZE,
    KB_INDEX_LOCK_KEY,
    KbDescribeStatus,
    KbPointStatus,
    KbProcessStatus,
)
from app.core.exceptions import UnprocessableEntityError
from app.core.locking import redis_lock
from app.models.kb import (
    KbImageAsset,
    KbKnowledgePoint,
    KbMedia,
    KbSource,
    KbTranscriptSegment,
)
from app.services.kb.embedding_client import EmbeddingClient, build_embedding_client

logger = structlog.get_logger(__name__)

#: 行可见性判定：(实体, 素材, 源) → 是否物化向量（口径与检索行内过滤同源）
_KeepFn = Callable[[Any, KbMedia, KbSource], bool]
#: 嵌入输入文本：实体 → str（与 search_text 生成列同式）
_TextFn = Callable[[Any], str]


class _KindSpec(NamedTuple):
    """一类检索行的物化声明（模型 + 可见性 + 嵌入文本）。"""

    kind: str
    model: Any
    keep_row: _KeepFn
    text_of: _TextFn


async def run_index(
    session: AsyncSession, *, force_rebuild: bool = False
) -> dict[str, Any]:
    """执行一轮嵌入物化（增量或全量重嵌），返回统计（spider 据此判态）。"""
    async with redis_lock(KB_INDEX_LOCK_KEY, ttl=3600, blocking=False) as ok:
        if not ok:
            logger.info("kb_index_skipped_busy")
            return {"skippedBusy": 1}
        try:
            embed = await build_embedding_client(session)
        except UnprocessableEntityError:
            logger.info("kb_index_no_model_configured")
            return {"noModelConfigured": 1}
        dims = await embed.discover_dims()
        if dims != KB_EMBEDDING_DIMS:
            logger.warning(
                "kb_index_dimension_mismatch",
                expected=KB_EMBEDDING_DIMS,
                actual=dims,
            )
            return {
                "dimensionMismatch": 1,
                "expectedDims": KB_EMBEDDING_DIMS,
                "actualDims": dims,
            }
        phase = "rebuild" if force_rebuild else "incremental"
        stats: dict[str, Any] = {"phase": phase}
        if force_rebuild:
            for model in (KbKnowledgePoint, KbTranscriptSegment, KbImageAsset):
                await session.execute(update(model).values(embedding_dirty=True))
            await session.commit()
            stats["forceRebuild"] = 1
        stats.update(await _dirty_counts(session))
        failed: list[str] = []
        for spec in (_POINT_SPEC, _SEGMENT_SPEC, _IMAGE_SPEC):
            try:
                stats.update(
                    await _materialize(
                        session, embed, spec, drain=force_rebuild, phase=phase
                    )
                )
            except Exception as exc:  # noqa: BLE001
                await session.rollback()
                failed.append(spec.kind)
                logger.error(
                    "kb_index_kind_failed", kind=spec.kind, error=str(exc)[:300]
                )
        if failed:
            stats["failedKinds"] = failed
        logger.info("kb_index_done", **stats)
        return stats


async def _dirty_counts(session: AsyncSession) -> dict[str, int]:
    async def count(model: Any) -> int:
        result = await session.execute(
            select(func.count()).select_from(model).where(model.embedding_dirty)
        )
        return int(result.scalar_one())

    return {
        "dirtyPoints": await count(KbKnowledgePoint),
        "dirtySegments": await count(KbTranscriptSegment),
        "dirtyImages": await count(KbImageAsset),
    }


async def _materialize(
    session: AsyncSession,
    embed: EmbeddingClient,
    spec: _KindSpec,
    *,
    drain: bool,
    phase: str,
) -> dict[str, int]:
    """按声明物化一类行：可见行写向量、不可见行清向量、已处理行清脏。

    ``drain=False``（增量）单轮只处理一批；``drain=True``（全量重嵌）循环
    清完当前全部脏行。
    """
    embedded = cleared = 0
    last_id = 0
    while True:
        rows = (
            await session.execute(
                select(spec.model, KbMedia, KbSource)
                .join(KbMedia, spec.model.media_id == KbMedia.id)
                .join(KbSource, spec.model.source_id == KbSource.id)
                .where(spec.model.id > last_id, spec.model.embedding_dirty)
                .order_by(spec.model.id)
                .limit(KB_INDEX_BATCH_SIZE)
            )
        ).all()
        if not rows:
            break
        last_id = rows[-1][0].id
        keep = [(entity, media) for entity, media, src in rows if spec.keep_row(entity, media, src)]
        keep_ids = {entity.id for entity, _ in keep}
        embedded += await _write_embeddings(
            session, embed, spec, keep, phase=phase
        )
        dead_ids = [entity.id for entity, _m, _s in rows if entity.id not in keep_ids]
        if dead_ids:
            await session.execute(
                update(spec.model)
                .where(spec.model.id.in_(dead_ids))
                .values(embedding=None)
            )
            cleared += len(dead_ids)
        await _clear_dirty(session, spec.model, [entity.id for entity, _m, _s in rows])
        if not drain:
            break
    return {f"{spec.kind}sEmbedded": embedded, f"{spec.kind}sCleared": cleared}


async def _write_embeddings(
    session: AsyncSession,
    embed: EmbeddingClient,
    spec: _KindSpec,
    pairs: list[tuple[Any, KbMedia]],
    *,
    phase: str,
) -> int:
    """批量嵌入并按行写回 ``embedding``（executemany，随清脏同事务提交）。"""
    if not pairs:
        return 0
    # 批次可能跨知识库：仅当全部行同源时记 sourceId（用量按库归集；跨源批不归集任何库）
    source_ids = {media.source_id for _, media in pairs}
    detail: dict[str, Any] = {"purpose": "kb_index", "phase": phase, "kind": spec.kind}
    if len(source_ids) == 1:
        detail["sourceId"] = source_ids.pop()
    vectors = await embed.embed_batched(
        [spec.text_of(entity) for entity, _ in pairs],
        detail=detail,
    )
    await session.execute(
        update(spec.model),
        [
            {"id": entity.id, "embedding": vector}
            for (entity, _media), vector in zip(pairs, vectors)
        ],
    )
    return len(pairs)


async def _clear_dirty(
    session: AsyncSession, model: Any, ids: list[int]
) -> None:
    """清掉本轮已处理行的脏标并提交（本轮向量写入同事务收口）。"""
    if ids:
        await session.execute(
            update(model).where(model.id.in_(ids)).values(embedding_dirty=False)
        )
    await session.commit()


# ---------------------------------------------------------------------------
# 三类检索行的可见性与嵌入文本（口径与 search_service 行内过滤同源）
# ---------------------------------------------------------------------------


def _source_indexable(src: KbSource) -> bool:
    """知识源可检索条件（arch/09 §7.1：enabled=false 或软删不进检索面）。"""
    return src.enabled and src.deleted_at is None


def _point_visible(p: KbKnowledgePoint, m: KbMedia, src: KbSource) -> bool:
    """知识点：published 且素材/知识源存活启用。"""
    return (
        _source_indexable(src)
        and p.status == KbPointStatus.PUBLISHED
        and m.deleted_at is None
    )


def _segment_visible(s: KbTranscriptSegment, m: KbMedia, src: KbSource) -> bool:
    """内容分段：done 素材存活且有文本。"""
    return (
        _source_indexable(src)
        and m.deleted_at is None
        and m.process_status == KbProcessStatus.DONE
        and bool(s.text.strip())
    )


def _image_visible(i: KbImageAsset, m: KbMedia, src: KbSource) -> bool:
    """图片资产：描述 done、未排除、素材存活且有文本。"""
    return (
        _source_indexable(src)
        and m.deleted_at is None
        and i.describe_status == KbDescribeStatus.DONE
        and not i.index_excluded
        and bool(_image_text(i).strip())
    )


def _point_text(p: KbKnowledgePoint) -> str:
    """知识点嵌入文本（与 ``search_text`` 生成列同式：非空段换行拼接）。"""
    return "\n".join(
        part for part in (p.title, p.term_definition, p.body, p.applicable_scene)
        if part
    )


def _segment_text(s: KbTranscriptSegment) -> str:
    """分段嵌入文本（词面/嵌入均直接用 ``text`` 列）。"""
    return s.text


def _image_text(i: KbImageAsset) -> str:
    """图片嵌入文本（与 ``search_text`` 生成列同式：三文本非空拼接）。"""
    return "\n".join(
        part for part in (i.text_in_image, i.caption, i.vision_description) if part
    )


_POINT_SPEC = _KindSpec("point", KbKnowledgePoint, _point_visible, _point_text)
_SEGMENT_SPEC = _KindSpec("segment", KbTranscriptSegment, _segment_visible, _segment_text)
_IMAGE_SPEC = _KindSpec("image", KbImageAsset, _image_visible, _image_text)


# ---------------------------------------------------------------------------
# 脏传播（软删/恢复/启停切换，下轮物化清/写向量；不 commit）
# ---------------------------------------------------------------------------


async def mark_media_children_dirty(session: AsyncSession, media_id: int) -> None:
    """素材软删/恢复时置脏全部子行（下轮 kb-index 写清向量；不 commit）。"""
    await session.execute(
        update(KbKnowledgePoint)
        .where(KbKnowledgePoint.media_id == media_id)
        .values(embedding_dirty=True)
    )
    await session.execute(
        update(KbTranscriptSegment)
        .where(KbTranscriptSegment.media_id == media_id)
        .values(embedding_dirty=True)
    )
    await session.execute(
        update(KbImageAsset)
        .where(KbImageAsset.media_id == media_id)
        .values(embedding_dirty=True)
    )


async def mark_source_children_dirty(session: AsyncSession, source_id: int) -> None:
    """知识源软删/恢复时置脏全部子行（语义同 ``mark_media_children_dirty``）。"""
    await session.execute(
        update(KbKnowledgePoint)
        .where(KbKnowledgePoint.source_id == source_id)
        .values(embedding_dirty=True)
    )
    await session.execute(
        update(KbTranscriptSegment)
        .where(KbTranscriptSegment.source_id == source_id)
        .values(embedding_dirty=True)
    )
    await session.execute(
        update(KbImageAsset)
        .where(KbImageAsset.source_id == source_id)
        .values(embedding_dirty=True)
    )
