"""知识库 ES 索引服务（kb-index internal 任务的执行体，arch/12 §5）。

PG 是唯一真相源，ES 是可重建检索投影：索引 ``kb-knowledge-v{N}`` 经别名
``kb-knowledge`` 承载三类文档（point/segment/image）的 BM25 + 向量混合检索。

- **增量**（默认，*/5 cron）：扫描三类 ``embedding_dirty`` 行——published 点 /
  done 素材分段 / 已描述未排除图片 upsert，rejected 点、软删素材子行、排除
  图片删文档；单轮各类限量，余量下轮续跑；
- **蓝绿重建**（``force_rebuild``，后台手动触发）：新版本索引全量灌入 →
  文档数对账 → 原子切别名 → 按 ``updated_at`` 清开始前的脏行（重建期间的
  新编辑留待下轮增量）→ 清理超龄无别名旧版本（回退观察窗）；
- **指纹**：索引 ``mappings._meta.kb_fingerprint``（config_id:模型:维度；
  ES 8.x 已移除 ``index.meta.*`` 自定义设置），与当前 embedding 槽位不符时
  SKIPPED，需人工触发重建。

文档 id 为 ``{kind}-{pg_id}``（确定性，upsert 幂等）。删除类兜底（清理硬删/
转写重灌）走 best-effort delete_by_query，失败仅记日志——投影可重建，不阻塞主链路。
"""

from collections.abc import Callable
from datetime import timedelta
from typing import Any

import structlog
from elasticsearch import AsyncElasticsearch, NotFoundError
from elasticsearch.helpers import async_bulk
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.kb import (
    KB_INDEX_ALIAS,
    KB_INDEX_BATCH_SIZE,
    KB_INDEX_LOCK_KEY,
    KB_INDEX_PRUNE_DAYS,
    KbDescribeStatus,
    KbPointStatus,
    KbProcessStatus,
)
from app.core.clock import utc_now
from app.core.config import get_settings
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

_INDEX_PREFIX = "kb-knowledge-v"
_FINGERPRINT_KEY = "kb_fingerprint"
_EMBED_TEXT_MAX_CHARS = 6000

#: (实体, 素材) 对 → (doc_id, doc, 嵌入文本)
_Projector = Callable[[Any, KbMedia], tuple[str, dict[str, Any], str]]


class KbIndexError(RuntimeError):
    """索引构建失败（创建失败/对账不符，任务 FAILED 由调度重试）。"""


class _FingerprintMismatchError(RuntimeError):
    """当前 embedding 配置与索引指纹不符（转 SKIPPED，人工触发重建）。"""


async def run_index(
    session: AsyncSession, *, force_rebuild: bool = False
) -> dict[str, Any]:
    """执行一轮索引构建（增量或蓝绿重建），返回统计（spider 据此判态）。"""
    async with redis_lock(KB_INDEX_LOCK_KEY, ttl=3600, blocking=False) as ok:
        if not ok:
            logger.info("kb_index_skipped_busy")
            return {"skippedBusy": 1}
        try:
            embed = await build_embedding_client(session)
        except UnprocessableEntityError:
            logger.info("kb_index_no_model_configured")
            return {"noModelConfigured": 1}
        es = AsyncElasticsearch(get_settings().elasticsearch_url)
        try:
            if force_rebuild:
                return await _rebuild(session, es, embed)
            return await _incremental(session, es, embed)
        finally:
            await es.close()


# ---------------------------------------------------------------------------
# 增量：三类脏行扫描批量推进
# ---------------------------------------------------------------------------


async def _incremental(
    session: AsyncSession, es: AsyncElasticsearch, embed: EmbeddingClient
) -> dict[str, Any]:
    dirty = await _dirty_counts(session)
    if sum(dirty.values()) == 0:
        return {"nothingDirty": 1}
    try:
        index_name = await _resolve_index(es, embed)
    except _FingerprintMismatchError as exc:
        logger.warning("kb_index_fingerprint_mismatch", detail=str(exc))
        return {"fingerprintMismatch": 1, **dirty}
    stats: dict[str, Any] = dict(dirty)
    failed: list[str] = []
    for kind, sync in (
        ("point", _sync_points),
        ("segment", _sync_segments),
        ("image", _sync_images),
    ):
        try:
            stats.update(await sync(session, es, embed, index_name, force_all=False))
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            failed.append(kind)
            logger.error("kb_index_kind_failed", kind=kind, error=str(exc)[:300])
    if failed:
        stats["failedKinds"] = failed
    logger.info("kb_index_incremental_done", index=index_name, **stats)
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


async def _sync_points(
    session: AsyncSession,
    es: AsyncElasticsearch,
    embed: EmbeddingClient,
    index_name: str,
    *,
    force_all: bool,
) -> dict[str, int]:
    """知识点：published 且素材/知识源存活启用 → upsert，其余 → 删文档。"""
    indexed = deleted = 0
    processed: list[int] = []
    last_id = 0
    while True:
        conditions: list[Any] = [KbKnowledgePoint.id > last_id]
        if not force_all:
            conditions.append(KbKnowledgePoint.embedding_dirty)
        rows = (
            await session.execute(
                select(KbKnowledgePoint, KbMedia, KbSource)
                .join(KbMedia, KbKnowledgePoint.media_id == KbMedia.id)
                .join(KbSource, KbKnowledgePoint.source_id == KbSource.id)
                .where(*conditions)
                .order_by(KbKnowledgePoint.id)
                .limit(KB_INDEX_BATCH_SIZE)
            )
        ).all()
        if not rows:
            break
        last_id = rows[-1][0].id
        processed.extend(p.id for p, _, _src in rows)
        keep = [
            (p, m)
            for p, m, src in rows
            if _source_indexable(src)
            and p.status == KbPointStatus.PUBLISHED
            and m.deleted_at is None
        ]
        keep_ids = {p.id for p, _ in keep}
        indexed += await _write_docs(
            es, embed, index_name, "point", keep, _point_doc, force_all=force_all
        )
        dead = [f"point-{p.id}" for p, _, _src in rows if p.id not in keep_ids]
        await _remove_docs(es, index_name, dead)
        deleted += len(dead)
        if not force_all:
            await _clear_dirty(session, KbKnowledgePoint, processed)
            break
    return {"pointsIndexed": indexed, "pointsDeleted": deleted}


async def _sync_segments(
    session: AsyncSession,
    es: AsyncElasticsearch,
    embed: EmbeddingClient,
    index_name: str,
    *,
    force_all: bool,
) -> dict[str, int]:
    """内容分段：done 素材存活且有文本 → upsert，其余（软删/空文本）→ 删文档。"""
    indexed = deleted = 0
    processed: list[int] = []
    last_id = 0
    while True:
        conditions: list[Any] = [KbTranscriptSegment.id > last_id]
        if not force_all:
            conditions.append(KbTranscriptSegment.embedding_dirty)
        rows = (
            await session.execute(
                select(KbTranscriptSegment, KbMedia, KbSource)
                .join(KbMedia, KbTranscriptSegment.media_id == KbMedia.id)
                .join(KbSource, KbTranscriptSegment.source_id == KbSource.id)
                .where(*conditions)
                .order_by(KbTranscriptSegment.id)
                .limit(KB_INDEX_BATCH_SIZE)
            )
        ).all()
        if not rows:
            break
        last_id = rows[-1][0].id
        processed.extend(s.id for s, _, _src in rows)
        keep = [
            (s, m)
            for s, m, src in rows
            if _source_indexable(src)
            and m.deleted_at is None
            and m.process_status == KbProcessStatus.DONE
            and s.text.strip()
        ]
        keep_ids = {s.id for s, _ in keep}
        indexed += await _write_docs(
            es, embed, index_name, "segment", keep, _segment_doc, force_all=force_all
        )
        dead = [f"seg-{s.id}" for s, _, _src in rows if s.id not in keep_ids]
        await _remove_docs(es, index_name, dead)
        deleted += len(dead)
        if not force_all:
            await _clear_dirty(session, KbTranscriptSegment, processed)
            break
    return {"segmentsIndexed": indexed, "segmentsDeleted": deleted}


async def _sync_images(
    session: AsyncSession,
    es: AsyncElasticsearch,
    embed: EmbeddingClient,
    index_name: str,
    *,
    force_all: bool,
) -> dict[str, int]:
    """图片资产：done 未排除素材存活且有文本 → upsert，其余（排除/软删）→ 删文档。"""
    indexed = deleted = 0
    processed: list[int] = []
    last_id = 0
    while True:
        conditions: list[Any] = [KbImageAsset.id > last_id]
        if not force_all:
            conditions.append(KbImageAsset.embedding_dirty)
        rows = (
            await session.execute(
                select(KbImageAsset, KbMedia, KbSource)
                .join(KbMedia, KbImageAsset.media_id == KbMedia.id)
                .join(KbSource, KbImageAsset.source_id == KbSource.id)
                .where(*conditions)
                .order_by(KbImageAsset.id)
                .limit(KB_INDEX_BATCH_SIZE)
            )
        ).all()
        if not rows:
            break
        last_id = rows[-1][0].id
        processed.extend(i.id for i, _, _src in rows)
        keep = [
            (i, m)
            for i, m, src in rows
            if _source_indexable(src)
            and m.deleted_at is None
            and i.describe_status == KbDescribeStatus.DONE
            and not i.index_excluded
            and _image_text(i).strip()
        ]
        keep_ids = {i.id for i, _ in keep}
        indexed += await _write_docs(
            es, embed, index_name, "image", keep, _image_doc, force_all=force_all
        )
        dead = [f"img-{i.id}" for i, _, _src in rows if i.id not in keep_ids]
        await _remove_docs(es, index_name, dead)
        deleted += len(dead)
        if not force_all:
            await _clear_dirty(session, KbImageAsset, processed)
            break
    return {"imagesIndexed": indexed, "imagesDeleted": deleted}


def _source_indexable(src: KbSource) -> bool:
    """知识源可索引条件（arch/12 §7.1：enabled=false 或软删不进索引）。"""
    return src.enabled and src.deleted_at is None


async def _clear_dirty(
    session: AsyncSession, model: Any, ids: list[int]
) -> None:
    """清掉本轮已处理行的脏标并提交（增量路径单事务收口）。"""
    if ids:
        await session.execute(
            update(model).where(model.id.in_(ids)).values(embedding_dirty=False)
        )
    await session.commit()


async def _write_docs(
    es: AsyncElasticsearch,
    embed: EmbeddingClient,
    index_name: str,
    kind: str,
    pairs: list[tuple[Any, KbMedia]],
    project: _Projector,
    *,
    force_all: bool,
) -> int:
    """批量嵌入并 bulk upsert（文档 id 确定性，重复执行幂等覆盖）。"""
    projected = [project(entity, media) for entity, media in pairs]
    if not projected:
        return 0
    vectors = await embed.embed_batched(
        [text for _, _, text in projected],
        detail={
            "purpose": "kb_index",
            "phase": "rebuild" if force_all else "incremental",
            "kind": kind,
        },
    )
    actions = []
    for (doc_id, doc, _), vector in zip(projected, vectors):
        doc["embedding"] = vector
        actions.append(
            {"_op_type": "index", "_index": index_name, "_id": doc_id, "_source": doc}
        )
    await async_bulk(es, actions)
    return len(actions)


async def _remove_docs(
    es: AsyncElasticsearch, index_name: str, doc_ids: list[str]
) -> None:
    """批量删文档（缺文档的 delete 是良性 404，不视为错误）。"""
    if not doc_ids:
        return
    _, errors = await async_bulk(
        es,
        [
            {"_op_type": "delete", "_index": index_name, "_id": doc_id}
            for doc_id in doc_ids
        ],
        raise_on_error=False,
    )
    if errors:
        # raise_on_error=False 时返回值为失败计数（int）或明细列表
        failed = len(errors) if isinstance(errors, list) else int(errors)
        logger.warning("kb_index_delete_partial", failed=failed)


def _point_doc(p: KbKnowledgePoint, m: KbMedia) -> tuple[str, dict[str, Any], str]:
    text = _clip(
        "\n".join(
            part for part in (p.title, p.term_definition, p.body, p.applicable_scene)
            if part
        )
    )
    doc = {
        "doc_kind": "point",
        "source_id": p.source_id,
        "media_id": p.media_id,
        "media_kind": m.media_kind,
        "episode_no": m.episode_no,
        "point_type": p.point_type,
        "text": text,
        "start_ms": p.start_ms,
        "end_ms": p.end_ms,
        "page_start": p.page_start,
        "page_end": p.page_end,
    }
    return f"point-{p.id}", doc, text


def _segment_doc(
    s: KbTranscriptSegment, m: KbMedia
) -> tuple[str, dict[str, Any], str]:
    text = _clip(s.text)
    doc = {
        "doc_kind": "segment",
        "source_id": s.source_id,
        "media_id": s.media_id,
        "media_kind": m.media_kind,
        "episode_no": m.episode_no,
        "point_type": None,
        "text": text,
        "start_ms": s.start_ms,
        "end_ms": s.end_ms,
        "page_start": s.page_start,
        "page_end": s.page_end,
    }
    return f"seg-{s.id}", doc, text


def _image_text(i: KbImageAsset) -> str:
    return "\n".join(
        part for part in (i.text_in_image, i.caption, i.vision_description) if part
    )


def _image_doc(i: KbImageAsset, m: KbMedia) -> tuple[str, dict[str, Any], str]:
    text = _clip(_image_text(i))
    doc = {
        "doc_kind": "image",
        "source_id": i.source_id,
        "media_id": i.media_id,
        "media_kind": m.media_kind,
        "episode_no": m.episode_no,
        "point_type": None,
        "page_no": i.page_no,
        "text": text,
        "start_ms": i.start_ms,
        "end_ms": i.end_ms,
    }
    return f"img-{i.id}", doc, text


def _clip(text: str) -> str:
    return text[:_EMBED_TEXT_MAX_CHARS]


# ---------------------------------------------------------------------------
# 索引版本管理：bootstrap / 指纹 / 蓝绿重建
# ---------------------------------------------------------------------------


async def _resolve_index(es: AsyncElasticsearch, embed: EmbeddingClient) -> str:
    """定位写入目标：别名缺失时 bootstrap v1，指纹不符抛 _FingerprintMismatchError。"""
    dims = await embed.discover_dims()
    fingerprint = _fingerprint_of(embed, dims)
    current = await _aliased_versions(es)
    if not current:
        name = f"{_INDEX_PREFIX}1"
        await _create_index(es, name, fingerprint=fingerprint, dims=dims)
        await es.indices.update_aliases(
            actions=[{"add": {"index": name, "alias": KB_INDEX_ALIAS}}]
        )
        logger.info("kb_index_bootstrapped", index=name, fingerprint=fingerprint)
        return name
    name = current[0]
    mappings = (await es.indices.get_mapping(index=name))[name]["mappings"]
    stored = (mappings.get("_meta") or {}).get(_FINGERPRINT_KEY)
    if stored != fingerprint:
        raise _FingerprintMismatchError(
            f"index={name} stored={stored} current={fingerprint}"
        )
    return name


def _fingerprint_of(embed: EmbeddingClient, dims: int) -> str:
    """索引指纹：embedding 配置 + 模型名 + 实测维度（任一变更须重建）。"""
    return f"{embed.config_id}:{embed.model_name}:{dims}"


async def _aliased_versions(es: AsyncElasticsearch) -> list[str]:
    """当前挂别名的物理索引（正常至多一个）。"""
    try:
        resp = await es.indices.get_alias(name=KB_INDEX_ALIAS)
    except NotFoundError:
        return []
    return list(resp.keys())


async def _existing_versions(es: AsyncElasticsearch) -> list[tuple[str, int]]:
    """全部版本索引（含未挂别名的待清理/回退候选）。"""
    try:
        resp = await es.indices.get(index=f"{_INDEX_PREFIX}*")
    except NotFoundError:
        return []
    versions = []
    for name in resp:
        suffix = name.rsplit("v", 1)[-1]
        if suffix.isdigit():
            versions.append((name, int(suffix)))
    return versions


async def _create_index(
    es: AsyncElasticsearch, name: str, *, fingerprint: str, dims: int
) -> None:
    # 指纹放 mappings._meta：ES 8.x 已移除 index.meta.* 自定义设置（实测 400）
    mapping = _mapping(dims)
    mapping["_meta"] = {_FINGERPRINT_KEY: fingerprint}
    await es.indices.create(
        index=name,
        settings={
            "index": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
            }
        },
        mappings=mapping,
    )


def _mapping(dims: int) -> dict[str, Any]:
    """三类文档共用 mapping：单 BM25 text + dense_vector + 检索过滤字段。"""
    return {
        "dynamic": "strict",
        "properties": {
            "doc_kind": {"type": "keyword"},
            "source_id": {"type": "long"},
            "media_id": {"type": "long"},
            "media_kind": {"type": "keyword"},
            "episode_no": {"type": "integer"},
            "point_type": {"type": "keyword"},
            "page_no": {"type": "integer"},
            "text": {"type": "text"},
            "embedding": {
                "type": "dense_vector",
                "dims": dims,
                "index": True,
                "similarity": "cosine",
            },
            "start_ms": {"type": "long"},
            "end_ms": {"type": "long"},
            "page_start": {"type": "integer"},
            "page_end": {"type": "integer"},
        },
    }


async def _rebuild(
    session: AsyncSession, es: AsyncElasticsearch, embed: EmbeddingClient
) -> dict[str, Any]:
    """蓝绿全量重建：建新版本 → 全量灌入 → 对账 → 原子切别名 → 清脏 → 清理。"""
    started = utc_now()
    dims = await embed.discover_dims()
    fingerprint = _fingerprint_of(embed, dims)
    next_version = max((v for _, v in await _existing_versions(es)), default=0) + 1
    name = f"{_INDEX_PREFIX}{next_version}"
    await _create_index(es, name, fingerprint=fingerprint, dims=dims)
    stats: dict[str, Any] = {
        "rebuildVersion": next_version,
        "rebuildFingerprint": fingerprint,
    }
    stats.update(await _sync_points(session, es, embed, name, force_all=True))
    stats.update(await _sync_segments(session, es, embed, name, force_all=True))
    stats.update(await _sync_images(session, es, embed, name, force_all=True))
    expected = (
        stats.get("pointsIndexed", 0)
        + stats.get("segmentsIndexed", 0)
        + stats.get("imagesIndexed", 0)
    )
    # bulk 默认不 refresh，对账前强制刷新可见性
    await es.indices.refresh(index=name)
    actual = int((await es.count(index=name))["count"])
    if actual != expected:
        raise KbIndexError(f"索引重建对账不符：期望 {expected}，实际 {actual}")
    await _switch_alias(es, name)
    # 只清重建开始前已存在的脏行；期间的新编辑保持脏，下轮增量补
    await session.execute(
        update(KbKnowledgePoint)
        .where(KbKnowledgePoint.embedding_dirty, KbKnowledgePoint.updated_at < started)
        .values(embedding_dirty=False)
    )
    await session.execute(
        update(KbTranscriptSegment)
        .where(
            KbTranscriptSegment.embedding_dirty,
            KbTranscriptSegment.updated_at < started,
        )
        .values(embedding_dirty=False)
    )
    await session.execute(
        update(KbImageAsset)
        .where(KbImageAsset.embedding_dirty, KbImageAsset.updated_at < started)
        .values(embedding_dirty=False)
    )
    await session.commit()
    stats["prunedVersions"] = await _prune_stale(es)
    logger.info("kb_index_rebuilt", index=name, **stats)
    return stats


async def _switch_alias(es: AsyncElasticsearch, name: str) -> None:
    """原子切换别名（单次 _aliases 调用，读端无感）。"""
    actions = [
        {"remove": {"index": old, "alias": KB_INDEX_ALIAS}}
        for old in await _aliased_versions(es)
    ]
    actions.append({"add": {"index": name, "alias": KB_INDEX_ALIAS}})
    await es.indices.update_aliases(actions=actions)


async def _prune_stale(es: AsyncElasticsearch) -> int:
    """删除超龄且未挂别名的旧版本（保留 7 天回退观察窗）。"""
    cutoff_ms = (utc_now() - timedelta(days=KB_INDEX_PRUNE_DAYS)).timestamp() * 1000
    aliased = set(await _aliased_versions(es))
    pruned = 0
    for name, _ in await _existing_versions(es):
        if name in aliased:
            continue
        settings = (await es.indices.get(index=name))[name]["settings"]["index"]
        try:
            created = float(settings.get("creation_date") or 0)
        except (TypeError, ValueError):
            continue
        if created < cutoff_ms:
            await es.indices.delete(index=name)
            pruned += 1
    return pruned


# ---------------------------------------------------------------------------
# 删除类兜底（清理任务/转写重灌调用，best-effort）
# ---------------------------------------------------------------------------


async def delete_docs_for_media(media_ids: list[int]) -> None:
    """素材硬删后清投影文档（kb-cleanup 兜底）。"""
    await _delete_by_terms({"media_id": media_ids})


async def mark_media_children_dirty(session: AsyncSession, media_id: int) -> None:
    """素材软删/恢复时置脏全部子行（下轮 kb-index 增删投影文档；不 commit）。"""
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


async def delete_docs_for_source(source_ids: list[int]) -> None:
    """知识源硬删后清投影文档（kb-cleanup 兜底）。"""
    await _delete_by_terms({"source_id": source_ids})


async def delete_segment_docs(media_id: int) -> None:
    """转写重灌前清该素材旧分段文档（旧行将被删除，脏标不会命中）。"""
    await _delete_by_terms({"media_id": [media_id]}, doc_kind="segment")


async def _delete_by_terms(
    terms: dict[str, list[int]], *, doc_kind: str | None = None
) -> None:
    if not any(terms.values()):
        return
    filters: list[dict[str, Any]] = [
        {"terms": {field: values for field, values in terms.items()}}
    ]
    if doc_kind is not None:
        filters.append({"term": {"doc_kind": doc_kind}})
    es = AsyncElasticsearch(get_settings().elasticsearch_url)
    try:
        await es.delete_by_query(
            index=KB_INDEX_ALIAS,
            query={"bool": {"filter": filters}},
            conflicts="proceed",
        )
    except NotFoundError:
        pass  # 索引尚未 bootstrap，无文档可删
    except Exception as exc:  # noqa: BLE001
        logger.warning("kb_index_delete_by_query_failed", error=str(exc)[:300])
    finally:
        await es.close()
