"""索引服务单测：三类脏行增量推进、bootstrap/指纹校验、蓝绿重建（ES/embedding 全 mock）。"""

from contextlib import ExitStack, asynccontextmanager
from datetime import timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from elasticsearch import NotFoundError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.clock import utc_now
from app.core.database import Base
from app.models.kb import (
    KbImageAsset,
    KbKnowledgePoint,
    KbMedia,
    KbSource,
    KbTranscriptSegment,
)
from app.services.kb import index_service
from app.services.kb.embedding_client import EmbeddingClient

pytestmark = pytest.mark.unit


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                KbSource.__table__,
                KbMedia.__table__,
                KbTranscriptSegment.__table__,
                KbKnowledgePoint.__table__,
                KbImageAsset.__table__,
            ],
        )
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as db:
        yield db
    await engine.dispose()


# ---------------------------------------------------------------------------
# mock 工具：ES 客户端 / embedding httpx / redis 锁
# ---------------------------------------------------------------------------


def _response(payload: dict[str, Any]) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = payload
    resp.text = ""
    return resp


def _payload(count: int, *, dim: int = 4) -> dict[str, Any]:
    return {
        "data": [
            {"index": i, "embedding": [float(i)] * dim}
            for i in reversed(range(count))
        ],
        "usage": {"prompt_tokens": 1, "total_tokens": 1},
    }


def _embed_client() -> EmbeddingClient:
    return EmbeddingClient(
        config_id=3,
        provider="custom",
        base_url="https://gw.example.com/v1",
        api_key="sk-test",
        model_name="embedding-3",
    )


def _es_mock(
    *,
    alias: dict[str, Any] | None = None,
    alias_missing: bool = False,
    fingerprint: str | None = None,
    versions: dict[str, dict[str, Any]] | None = None,
    count: int = 0,
) -> MagicMock:
    es = MagicMock()
    es.indices = MagicMock()
    es.indices.create = AsyncMock()
    es.indices.update_aliases = AsyncMock()
    es.indices.delete = AsyncMock()

    async def _get_alias(name: str) -> dict[str, Any]:
        if alias_missing:
            meta = SimpleNamespace(
                status=404, http_version="1.1", headers={}, duration=0.0
            )
            raise NotFoundError("alias missing", meta, {})
        return alias or {}

    es.indices.get_alias = AsyncMock(side_effect=_get_alias)

    settings_map = dict(versions or {})
    if fingerprint is not None:
        settings_map["kb-knowledge-v1"] = {
            "settings": {"index": {"creation_date": "1000"}}
        }
    mapping_map: dict[str, dict[str, Any]] = {}
    if fingerprint is not None:
        mapping_map["kb-knowledge-v1"] = {
            "mappings": {"_meta": {"kb_fingerprint": fingerprint}}
        }

    async def _get(index: str) -> dict[str, Any]:
        # 真实 API 返回 {索引名: body}；模式查询返回全部命中的同名映射
        if index.endswith("*"):
            return settings_map
        return {index: settings_map.get(index, {})}

    async def _get_mapping(index: str) -> dict[str, Any]:
        return {index: mapping_map.get(index, {"mappings": {}})}

    es.indices.get = AsyncMock(side_effect=_get)
    es.indices.get_mapping = AsyncMock(side_effect=_get_mapping)
    es.indices.refresh = AsyncMock()
    es.count = AsyncMock(return_value={"count": count})
    es.delete_by_query = AsyncMock()
    es.close = AsyncMock()
    return es


def _patches(es: MagicMock, bulk: AsyncMock) -> list[Any]:
    @asynccontextmanager
    async def fake_lock(*args: Any, **kwargs: Any):
        yield True

    post = AsyncMock(
        side_effect=lambda url, **kw: _response(
            payload=_payload(len(kw["json"]["input"]))
        )
    )
    http_cls = MagicMock()
    http_cls.return_value.__aenter__.return_value.post = post
    return [
        patch("app.services.kb.index_service.redis_lock", side_effect=fake_lock),
        patch(
            "app.services.kb.index_service.build_embedding_client",
            new=AsyncMock(return_value=_embed_client()),
        ),
        patch("app.services.kb.index_service.AsyncElasticsearch", return_value=es),
        patch("app.services.kb.index_service.async_bulk", new=bulk),
        patch("app.services.kb.embedding_client.httpx.AsyncClient", http_cls),
        patch("app.services.kb.embedding_client.enqueue", new=MagicMock()),
    ]


async def _seed_media(session: AsyncSession, *, deleted: bool = False) -> KbMedia:
    src = KbSource(source_type="course", name="课")
    session.add(src)
    await session.flush()
    media = KbMedia(
        source_id=src.id,
        media_kind="video",
        episode_no=1,
        title="第 1 集",
        file_name="e1.mp4",
        cos_key=f"kb/{src.id}/e1.mp4",
        file_hash="a" * 32,
        process_status="done",
        deleted_at=utc_now() if deleted else None,
    )
    session.add(media)
    await session.flush()
    return media


def _bulk_actions(bulk: AsyncMock) -> list[dict[str, Any]]:
    return [a for call in bulk.call_args_list for a in call.args[1]]


# ---------------------------------------------------------------------------
# 增量：三类脏行
# ---------------------------------------------------------------------------


async def test_incremental_upserts_and_deletes_by_kind(session: AsyncSession) -> None:
    media = await _seed_media(session)
    pub = KbKnowledgePoint(
        source_id=media.source_id,
        media_id=media.id,
        point_type="case",
        title="头肩顶案例",
        body="颈线突破后的量度目标",
        excerpt="头肩顶",
        status="published",
        embedding_dirty=True,
    )
    rej = KbKnowledgePoint(
        source_id=media.source_id,
        media_id=media.id,
        point_type="concept",
        title="驳回卡",
        body="旧内容",
        excerpt="旧",
        status="rejected",
        embedding_dirty=True,
    )
    seg = KbTranscriptSegment(
        source_id=media.source_id,
        media_id=media.id,
        seq_no=1,
        text="支撑位与压力位互换",
        start_ms=0,
        end_ms=5000,
    )
    img_ok = KbImageAsset(
        source_id=media.source_id,
        media_id=media.id,
        cos_key="kb/i1",
        describe_status="done",
        text_in_image="头肩顶",
        caption="图注",
        embedding_dirty=True,
    )
    img_ex = KbImageAsset(
        source_id=media.source_id,
        media_id=media.id,
        cos_key="kb/i2",
        describe_status="done",
        caption="被排除",
        embedding_dirty=True,
        index_excluded=True,
    )
    session.add_all([pub, rej, seg, img_ok, img_ex])
    await session.commit()

    bulk = AsyncMock(return_value=(0, []))
    es = _es_mock(alias={"kb-knowledge-v1": {}}, fingerprint="3:embedding-3:4")
    with ExitStack() as stack:
        for p in _patches(es, bulk):
            stack.enter_context(p)
        stats = await index_service.run_index(session)

    assert stats["pointsIndexed"] == 1
    assert stats["pointsDeleted"] == 1
    assert stats["segmentsIndexed"] == 1
    assert stats["imagesIndexed"] == 1
    assert stats["imagesDeleted"] == 1

    indexed = {
        a["_id"]: a["_source"] for a in _bulk_actions(bulk) if a["_op_type"] == "index"
    }
    deleted = [a["_id"] for a in _bulk_actions(bulk) if a["_op_type"] == "delete"]
    assert f"point-{pub.id}" in indexed
    point_doc = indexed[f"point-{pub.id}"]
    assert point_doc["doc_kind"] == "point"
    assert point_doc["media_kind"] == "video"
    assert "头肩顶案例" in point_doc["text"]
    assert point_doc["embedding"] == [0.0, 0.0, 0.0, 0.0]
    assert f"seg-{seg.id}" in indexed
    assert f"img-{img_ok.id}" in indexed
    assert {f"point-{rej.id}", f"img-{img_ex.id}"} == set(deleted)

    for row in (pub, rej, seg, img_ok, img_ex):
        await session.refresh(row)
        assert row.embedding_dirty is False


async def test_incremental_soft_deleted_media_routes_to_delete(
    session: AsyncSession,
) -> None:
    media = await _seed_media(session, deleted=True)
    point = KbKnowledgePoint(
        source_id=media.source_id,
        media_id=media.id,
        point_type="method",
        title="方法卡",
        body="内容",
        excerpt="摘",
        status="published",
        embedding_dirty=True,
    )
    session.add(point)
    await session.commit()

    bulk = AsyncMock(return_value=(0, []))
    es = _es_mock(alias={"kb-knowledge-v1": {}}, fingerprint="3:embedding-3:4")
    with ExitStack() as stack:
        for p in _patches(es, bulk):
            stack.enter_context(p)
        stats = await index_service.run_index(session)

    assert stats["pointsIndexed"] == 0
    assert stats["pointsDeleted"] == 1
    actions = _bulk_actions(bulk)
    assert [a["_id"] for a in actions] == [f"point-{point.id}"]
    assert actions[0]["_op_type"] == "delete"
    await session.refresh(point)
    assert point.embedding_dirty is False


async def test_incremental_disabled_source_routes_to_delete(
    session: AsyncSession,
) -> None:
    """停用知识源的 published 点不进索引（arch/12 §7.1 enabled=false 口径）。"""
    media = await _seed_media(session)
    source = await session.get(KbSource, media.source_id)
    assert source is not None
    source.enabled = False
    point = KbKnowledgePoint(
        source_id=media.source_id,
        media_id=media.id,
        point_type="concept",
        title="停用源卡片",
        body="内容",
        excerpt="摘",
        status="published",
        embedding_dirty=True,
    )
    session.add(point)
    await session.commit()

    bulk = AsyncMock(return_value=(0, []))
    es = _es_mock(alias={"kb-knowledge-v1": {}}, fingerprint="3:embedding-3:4")
    with ExitStack() as stack:
        for p in _patches(es, bulk):
            stack.enter_context(p)
        stats = await index_service.run_index(session)

    assert stats["pointsIndexed"] == 0
    assert stats["pointsDeleted"] == 1
    actions = _bulk_actions(bulk)
    assert [a["_id"] for a in actions] == [f"point-{point.id}"]
    assert actions[0]["_op_type"] == "delete"


async def test_incremental_bootstraps_v1(session: AsyncSession) -> None:
    media = await _seed_media(session)
    session.add(
        KbKnowledgePoint(
            source_id=media.source_id,
            media_id=media.id,
            point_type="concept",
            title="概念",
            body="内容",
            excerpt="摘",
            status="published",
            embedding_dirty=True,
        )
    )
    await session.commit()

    bulk = AsyncMock(return_value=(0, []))
    es = _es_mock(alias_missing=True)
    with ExitStack() as stack:
        for p in _patches(es, bulk):
            stack.enter_context(p)
        stats = await index_service.run_index(session)

    assert stats["pointsIndexed"] == 1
    es.indices.create.assert_awaited_once()
    kwargs = es.indices.create.call_args.kwargs
    assert kwargs["index"] == "kb-knowledge-v1"
    assert kwargs["mappings"]["_meta"] == {"kb_fingerprint": "3:embedding-3:4"}
    assert kwargs["mappings"]["properties"]["embedding"]["dims"] == 4
    es.indices.update_aliases.assert_awaited_once_with(
        actions=[{"add": {"index": "kb-knowledge-v1", "alias": "kb-knowledge"}}]
    )


async def test_incremental_fingerprint_mismatch_skips(session: AsyncSession) -> None:
    media = await _seed_media(session)
    session.add(
        KbTranscriptSegment(
            source_id=media.source_id, media_id=media.id, seq_no=1, text="脏行"
        )
    )
    await session.commit()

    bulk = AsyncMock(return_value=(0, []))
    es = _es_mock(alias={"kb-knowledge-v1": {}}, fingerprint="3:embedding-3:8")
    with ExitStack() as stack:
        for p in _patches(es, bulk):
            stack.enter_context(p)
        stats = await index_service.run_index(session)

    assert stats["fingerprintMismatch"] == 1
    bulk.assert_not_awaited()
    seg = await session.get(KbTranscriptSegment, 1)
    assert seg is not None
    assert seg.embedding_dirty is True


async def test_incremental_nothing_dirty_skips_before_es(session: AsyncSession) -> None:
    bulk = AsyncMock(return_value=(0, []))
    es = _es_mock(alias_missing=True)
    with ExitStack() as stack:
        for p in _patches(es, bulk):
            stack.enter_context(p)
        stats = await index_service.run_index(session)

    assert stats["nothingDirty"] == 1
    bulk.assert_not_awaited()
    es.indices.get_alias.assert_not_awaited()


# ---------------------------------------------------------------------------
# 蓝绿重建
# ---------------------------------------------------------------------------


async def test_rebuild_switches_alias_and_clears_stale_dirty(
    session: AsyncSession,
) -> None:
    media = await _seed_media(session)
    old_point = KbKnowledgePoint(
        source_id=media.source_id,
        media_id=media.id,
        point_type="theorem",
        title="定理",
        body="内容",
        excerpt="摘",
        status="published",
        embedding_dirty=True,
        updated_at=utc_now() - timedelta(days=1),
    )
    fresh_segment = KbTranscriptSegment(
        source_id=media.source_id,
        media_id=media.id,
        seq_no=1,
        text="重建期间的新编辑",
        embedding_dirty=True,
        updated_at=utc_now() + timedelta(seconds=5),
    )
    session.add_all([old_point, fresh_segment])
    await session.commit()

    bulk = AsyncMock(return_value=(0, []))
    es = _es_mock(
        alias={"kb-knowledge-v1": {}},
        versions={
            "kb-knowledge-v1": {"settings": {"index": {"creation_date": "1000"}}}
        },
        count=2,
    )
    with ExitStack() as stack:
        for p in _patches(es, bulk):
            stack.enter_context(p)
        stats = await index_service.run_index(session, force_rebuild=True)

    assert stats["rebuildVersion"] == 2
    assert stats["pointsIndexed"] == 1
    assert stats["segmentsIndexed"] == 1
    es.indices.create.assert_awaited_once()
    assert es.indices.create.call_args.kwargs["index"] == "kb-knowledge-v2"
    es.indices.update_aliases.assert_awaited_once_with(
        actions=[
            {"remove": {"index": "kb-knowledge-v1", "alias": "kb-knowledge"}},
            {"add": {"index": "kb-knowledge-v2", "alias": "kb-knowledge"}},
        ]
    )
    await session.refresh(old_point)
    await session.refresh(fresh_segment)
    assert old_point.embedding_dirty is False
    assert fresh_segment.embedding_dirty is True


async def test_rebuild_count_mismatch_raises(session: AsyncSession) -> None:
    media = await _seed_media(session)
    session.add(
        KbKnowledgePoint(
            source_id=media.source_id,
            media_id=media.id,
            point_type="concept",
            title="概念",
            body="内容",
            excerpt="摘",
            status="published",
            embedding_dirty=True,
        )
    )
    await session.commit()

    bulk = AsyncMock(return_value=(0, []))
    es = _es_mock(alias={"kb-knowledge-v1": {}}, count=99)
    with ExitStack() as stack:
        for p in _patches(es, bulk):
            stack.enter_context(p)
        with pytest.raises(index_service.KbIndexError, match="对账不符"):
            await index_service.run_index(session, force_rebuild=True)
    es.indices.update_aliases.assert_not_awaited()
