"""检索服务单测：RRF 融合黄金样本、过滤器透传、降级、前滚与水合防御（全 mock）。"""

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from elasticsearch import TransportError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.core.exceptions import NotFoundError, UnprocessableEntityError
from app.models.kb import (
    KbImageAsset,
    KbKnowledgePoint,
    KbMedia,
    KbSettings,
    KbSource,
    KbTranscriptSegment,
)
from app.services.kb import search_service
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
                KbSettings.__table__,
            ],
        )
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as db:
        db.add(KbSettings(id=1, top_k=8))
        await db.commit()
        yield db
    await engine.dispose()


def _es_mock(*, responses: list[dict[str, Any]] | None = None) -> MagicMock:
    es = MagicMock()
    hits = {"hits": {"hits": []}}
    if responses:
        es.search = AsyncMock(side_effect=responses)
    else:
        es.search = AsyncMock(return_value=hits)
    es.close = AsyncMock()
    return es


def _hits(*doc_ids: str) -> dict[str, Any]:
    return {"hits": {"hits": [{"_id": doc_id} for doc_id in doc_ids]}}


def _embed_client() -> EmbeddingClient:
    return EmbeddingClient(
        config_id=3,
        provider="custom",
        base_url="https://gw.example.com/v1",
        api_key="sk-test",
        model_name="embedding-3",
    )


def _patches(
    es: MagicMock,
    *,
    embed_fails: bool = False,
    presigned: str = "https://cos/thumb?sig=1",
) -> list[Any]:
    build = (
        AsyncMock(side_effect=UnprocessableEntityError("embedding 未配置"))
        if embed_fails
        else AsyncMock(return_value=_embed_client())
    )
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "data": [{"index": 0, "embedding": [0.1, 0.2, 0.3, 0.4]}],
        "usage": {"prompt_tokens": 1, "total_tokens": 1},
    }
    response.text = ""
    post = AsyncMock(return_value=response)
    http_cls = MagicMock()
    http_cls.return_value.__aenter__.return_value.post = post
    minio = MagicMock()
    minio.get_presigned_url = AsyncMock(return_value=presigned)
    return [
        patch("app.services.kb.search_service.AsyncElasticsearch", return_value=es),
        patch("app.services.kb.search_service.build_embedding_client", new=build),
        patch("app.services.kb.embedding_client.httpx.AsyncClient", http_cls),
        patch("app.services.kb.embedding_client.enqueue", new=MagicMock()),
        patch(
            "app.services.kb.search_service.get_minio_service",
            return_value=minio,
        ),
    ]


async def _seed(session: AsyncSession) -> dict[str, Any]:
    """课程知识源：2 published 点（含案例卡）+ 2 分段 + 2 帧。"""
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
    )
    session.add(media)
    await session.flush()
    p_case = KbKnowledgePoint(
        source_id=src.id,
        media_id=media.id,
        point_type="case",
        title="头肩顶案例",
        body="颈线突破后的量度目标",
        excerpt="你看这个头肩顶",
        status="published",
        chapter_path=["第一章", "形态"],
        start_ms=10_000,
        end_ms=40_000,
    )
    p_concept = KbKnowledgePoint(
        source_id=src.id,
        media_id=media.id,
        point_type="concept",
        title="支撑位",
        body="前低形成支撑",
        excerpt="支撑位与压力位互换",
        status="published",
        chapter_path=["第二章", "基础"],
        start_ms=50_000,
        end_ms=60_000,
    )
    p_rejected = KbKnowledgePoint(
        source_id=src.id,
        media_id=media.id,
        point_type="concept",
        title="被驳回",
        body="旧内容",
        excerpt="旧",
        status="rejected",
    )
    seg = KbTranscriptSegment(
        source_id=src.id,
        media_id=media.id,
        seq_no=1,
        text="支撑位与压力位互换",
        start_ms=9_000,
        end_ms=14_000,
    )
    frame_ok = KbImageAsset(
        source_id=src.id,
        media_id=media.id,
        cos_key="kb/f1",
        thumb_cos_key="kb/f1_thumb",
        describe_status="done",
        start_ms=15_000,
        caption="头肩顶颈线",
    )
    frame_ex = KbImageAsset(
        source_id=src.id,
        media_id=media.id,
        cos_key="kb/f2",
        describe_status="done",
        start_ms=16_000,
        caption="被排除帧",
        index_excluded=True,
    )
    session.add_all([p_case, p_concept, p_rejected, seg, frame_ok, frame_ex])
    await session.commit()
    return {
        "source": src,
        "media": media,
        "p_case": p_case,
        "p_concept": p_concept,
        "p_rejected": p_rejected,
        "seg": seg,
        "frame_ok": frame_ok,
        "frame_ex": frame_ex,
    }


# ---------------------------------------------------------------------------
# RRF 融合黄金样本
# ---------------------------------------------------------------------------


async def test_rrf_golden_sample_and_hydration(session: AsyncSession) -> None:
    """固定两路排名断言融合序：两路叠加者居首，水合字段与关联帧齐全。"""
    seeded = await _seed(session)
    # BM25: point-1(case), point-2(concept), seg-1；knn: seg-1, point-1, img-1
    es = _es_mock(
        responses=[
            _hits(f"point-{seeded['p_case'].id}", f"point-{seeded['p_concept'].id}",
                  f"seg-{seeded['seg'].id}"),
            _hits(f"seg-{seeded['seg'].id}", f"point-{seeded['p_case'].id}",
                  f"img-{seeded['frame_ok'].id}"),
        ]
    )
    with _mocked(es):
        result = await search_service.search(session, q="头肩顶 支撑位")

    # point-1 = 1/61 + 1/62 双路叠加居首 > seg-1 = 1/63 + 1/61 > point-2 > img-1
    assert [p.id for p in result.points] == [
        seeded["p_case"].id,
        seeded["p_concept"].id,
    ]
    assert result.points[0].score == pytest.approx(1 / 61 + 1 / 62)
    assert [s.id for s in result.segments] == [seeded["seg"].id]
    assert result.segments[0].score == pytest.approx(1 / 63 + 1 / 61)
    assert [i.id for i in result.images] == [seeded["frame_ok"].id]
    assert result.degraded is None

    case = result.points[0]
    assert case.point_type == "case"
    assert case.media_kind == "video"
    assert case.episode_no == 1
    assert case.media_title == "第 1 集"
    assert case.chapter_path == ["第一章", "形态"]
    assert case.frames and case.frames[0].caption == "头肩顶颈线"
    assert case.frames[0].thumb_url == "https://cos/thumb?sig=1"
    assert "https://" in result.images[0].thumb_url


async def test_rejected_point_doc_hit_is_filtered(session: AsyncSession) -> None:
    """投影滞后防御：文档命中但 PG 行已驳回/素材软删 → 不出水合。"""
    seeded = await _seed(session)
    es = _es_mock(
        responses=[_hits(f"point-{seeded['p_rejected'].id}"), _hits()]
    )
    with _mocked(es):
        result = await search_service.search(session, q="旧内容")
    assert result.points == []


async def test_seek_rewind_4s(session: AsyncSession) -> None:
    """课程命中起播点 = max(0, start_ms − 4000)。"""
    seeded = await _seed(session)
    seg2 = KbTranscriptSegment(
        source_id=seeded["source"].id,
        media_id=seeded["media"].id,
        seq_no=2,
        text="趋势线画法",
        start_ms=90_000,
        end_ms=95_000,
    )
    session.add(seg2)
    await session.commit()
    es = _es_mock(
        responses=[_hits(f"seg-{seg2.id}", f"seg-{seeded['seg'].id}"), _hits()]
    )
    with _mocked(es):
        result = await search_service.search(session, q="趋势线")
    assert [s.seek_ms for s in result.segments] == [86_000, 5_000]


async def test_filters_passthrough_to_both_paths(session: AsyncSession) -> None:
    """source/kind/point_type 过滤器同构透传 BM25 与 knn 两路。"""
    es = _es_mock(responses=[_hits(), _hits()])
    with _mocked(es):
        await search_service.search(
            session, q="支撑", source_id=5, point_type="case", kind="point"
        )
    assert es.search.await_count == 2
    for call in es.search.await_args_list:
        body = call.kwargs["body"]
        blob = str(body)
        assert "'doc_kind': 'point'" in blob or '"doc_kind": "point"' in blob
        assert "source_id" in blob and "point_type" in blob


async def test_es_unavailable_degrades_to_empty(session: AsyncSession) -> None:
    es = _es_mock()
    es.search = AsyncMock(side_effect=TransportError("N/A", "connection refused"))
    with _mocked(es):
        result = await search_service.search(session, q="任意")
    assert result.degraded == "es_unavailable"
    assert result.points == [] and result.segments == [] and result.images == []


async def test_embedding_unavailable_falls_back_to_bm25(
    session: AsyncSession,
) -> None:
    """embedding 槽位缺失：单路 BM25 继续服务并标记降级。"""
    seeded = await _seed(session)
    es = _es_mock(responses=[_hits(f"point-{seeded['p_case'].id}")])
    with _mocked(es, embed_fails=True):
        result = await search_service.search(session, q="头肩顶")
    assert result.degraded == "embedding_unavailable"
    assert es.search.await_count == 1  # 无 knn 二路
    assert [p.id for p in result.points] == [seeded["p_case"].id]


async def test_chapter_filter_pushed_down_to_es(session: AsyncSession) -> None:
    """章节过滤下推 ES filter context：两路查询都带前缀键 term 与卡片限定。"""
    es = _es_mock(responses=[_hits(), _hits()])
    with _mocked(es):
        await search_service.search(session, q="形态", chapter_path=["2", "2.5"])
    assert es.search.await_count == 2
    for call in es.search.await_args_list:
        blob = str(call.kwargs["body"])
        assert "'chapter_keys': '2/2.5'" in blob
        assert "'doc_kind': 'point'" in blob


async def test_chapter_prefix_hydration_defense_filters_stale_projection(
    session: AsyncSession,
) -> None:
    """投影滞后防御：文档命中但 PG chapter_path 已不在请求前缀内 → 不出水合。"""
    seeded = await _seed(session)
    es = _es_mock(
        responses=[_hits(f"point-{seeded['p_concept'].id}"), _hits()]
    )
    with _mocked(es):
        result = await search_service.search(
            session, q="支撑", chapter_path=["第一章"]
        )
    assert result.points == []


async def test_case_frame_window_and_exclusion(session: AsyncSession) -> None:
    """关联帧限命中时间窗外扩内且未排除（排除帧不出现）。"""
    seeded = await _seed(session)
    far_frame = KbImageAsset(
        source_id=seeded["source"].id,
        media_id=seeded["media"].id,
        cos_key="kb/f3",
        describe_status="done",
        start_ms=90_000,
        caption="窗外帧",
    )
    session.add(far_frame)
    await session.commit()
    es = _es_mock(responses=[_hits(f"point-{seeded['p_case'].id}"), _hits()])
    with _mocked(es):
        result = await search_service.search(session, q="头肩顶案例")
    frames = result.points[0].frames
    assert [f.caption for f in frames] == ["头肩顶颈线"]  # 排除帧/窗外帧都不在


async def test_excluded_image_hit_filtered(session: AsyncSession) -> None:
    """图片命中水合排除已排除/未描述行。"""
    seeded = await _seed(session)
    es = _es_mock(responses=[_hits(), _hits(f"img-{seeded['frame_ex'].id}")])
    with _mocked(es):
        result = await search_service.search(session, q="被排除帧")
    assert result.images == []


# ---------------------------------------------------------------------------
# 发布态章节树
# ---------------------------------------------------------------------------


async def test_published_chapters_excludes_draft(session: AsyncSession) -> None:
    src = KbSource(
        source_type="course",
        name="课",
        chapter_tree={
            "draft": [{"id": "d1", "title": "草稿章", "children": []}],
            "published": [
                {
                    "id": "p1",
                    "title": "生效章",
                    "children": [
                        {"id": "p1-1", "title": "生效节", "children": []}
                    ],
                }
            ],
        },
    )
    session.add(src)
    await session.commit()
    result = await search_service.get_published_chapters(session, src.id)
    assert [n.title for n in result.chapters] == ["生效章"]
    assert result.chapters[0].children[0].title == "生效节"


async def test_published_chapters_disabled_source_404(session: AsyncSession) -> None:
    src = KbSource(source_type="course", name="停用", enabled=False)
    session.add(src)
    await session.commit()
    with pytest.raises(NotFoundError):
        await search_service.get_published_chapters(session, src.id)


# ---------------------------------------------------------------------------
# 章节卡片清单（浏览路径）
# ---------------------------------------------------------------------------

_TREE = {
    "published": [
        {
            "id": "1",
            "title": "价值篇",
            "children": [{"id": "1.1", "title": "复利", "children": []}],
        },
        {"id": "2", "title": "估值篇", "children": []},
    ]
}


async def _seed_tree_source(session: AsyncSession) -> KbSource:
    src = KbSource(source_type="course", name="课", chapter_tree=_TREE)
    session.add(src)
    await session.commit()
    return src


async def test_list_chapter_points_validates_against_published_tree(
    session: AsyncSession,
) -> None:
    """空链/未知根/悬空链均 422；停用知识库 404。"""
    src = await _seed_tree_source(session)
    with pytest.raises(UnprocessableEntityError):
        await search_service.list_chapter_points(session, src.id, chapter_path=[])
    with pytest.raises(UnprocessableEntityError):
        await search_service.list_chapter_points(session, src.id, chapter_path=["9"])
    with pytest.raises(UnprocessableEntityError):
        await search_service.list_chapter_points(
            session, src.id, chapter_path=["1", "9.9"]
        )

    src.enabled = False
    await session.commit()
    with pytest.raises(NotFoundError):
        await search_service.list_chapter_points(
            session, src.id, chapter_path=["1"]
        )


async def test_list_chapter_points_assembles_paginated_cards(
    session: AsyncSession,
) -> None:
    """合法链透传仓储（含分页偏移），卡片字段齐全；零 total 跳过清单查询。"""
    seeded = await _seed(session)
    seeded["source"].chapter_tree = _TREE
    await session.commit()
    p = seeded["p_case"]
    with patch("app.services.kb.search_service.point_repository") as repo:
        repo.count_published_by_chapter = AsyncMock(return_value=1)
        repo.list_published_by_chapter = AsyncMock(
            return_value=[(p, 1, "第 1 集", "video")]
        )
        result = await search_service.list_chapter_points(
            session, seeded["source"].id, chapter_path=["1", "1.1"],
            page=2, page_size=5,
        )
    assert result.total == 1
    assert result.page == 2 and result.page_size == 5
    assert [item.id for item in result.points] == [p.id]
    item = result.points[0]
    assert item.media_kind == "video"
    assert item.media_title == "第 1 集"
    assert item.chapter_path == ["第一章", "形态"]
    assert item.start_ms == 10_000
    repo.list_published_by_chapter.assert_awaited_once_with(
        session, seeded["source"].id, ["1", "1.1"], offset=5, limit=5
    )

    with patch("app.services.kb.search_service.point_repository") as repo:
        repo.count_published_by_chapter = AsyncMock(return_value=0)
        repo.list_published_by_chapter = AsyncMock(return_value=[])
        result = await search_service.list_chapter_points(
            session, seeded["source"].id, chapter_path=["2"]
        )
    assert result.total == 0 and result.points == []
    repo.list_published_by_chapter.assert_not_awaited()


# ---------------------------------------------------------------------------
# 测试工具
# ---------------------------------------------------------------------------


@contextmanager
def _mocked(es: MagicMock, *, embed_fails: bool = False) -> Iterator[None]:
    """统一进出全部 patch（ES/embedding/minio）。"""
    with ExitStack() as stack:
        for p in _patches(es, embed_fails=embed_fails):
            stack.enter_context(p)
        yield
