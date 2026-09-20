"""检索服务单测：RRF 融合黄金样本、范围透传、降级、前滚与水合防御（双路 mock）。

双路召回（``_lexical_ranking``/``_vector_ranking``）依赖 PG 专属能力
（``search_text`` 生成列 / ``similarity()`` / halfvec ``<=>``），单测 mock
两路与查询向量，只钉融合、分桶、水合与降级逻辑。
"""

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
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
from app.services.kb.embedding_client import KbEmbeddingError

pytestmark = pytest.mark.unit

_QUERY_VEC = [0.1, 0.2, 0.3, 0.4]


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


@contextmanager
def _searching(
    lexical: list[str],
    vector: list[str] | None = None,
    *,
    query_vec: list[float] | None = _QUERY_VEC,
) -> Iterator[tuple[AsyncMock, AsyncMock]]:
    """统一 mock 双路召回与查询向量（minio 签名固定）。"""
    minio = MagicMock()
    minio.get_presigned_url = AsyncMock(return_value="https://cos/thumb?sig=1")
    with ExitStack() as stack:
        stack.enter_context(
            patch.object(
                search_service,
                "_query_vector",
                new=AsyncMock(return_value=query_vec),
            )
        )
        lex = stack.enter_context(
            patch.object(
                search_service, "_lexical_ranking", new=AsyncMock(return_value=lexical)
            )
        )
        vec = stack.enter_context(
            patch.object(
                search_service,
                "_vector_ranking",
                new=AsyncMock(return_value=vector if vector is not None else []),
            )
        )
        stack.enter_context(
            patch.object(
                search_service, "get_minio_service", return_value=minio
            )
        )
        yield lex, vec


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
    # 词面: point-1(case), point-2(concept), seg-1；向量: seg-1, point-1, img-1
    with _searching(
        [
            f"point-{seeded['p_case'].id}",
            f"point-{seeded['p_concept'].id}",
            f"seg-{seeded['seg'].id}",
        ],
        [
            f"seg-{seeded['seg'].id}",
            f"point-{seeded['p_case'].id}",
            f"img-{seeded['frame_ok'].id}",
        ],
    ):
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


async def test_rejected_point_hit_is_filtered_at_hydration(
    session: AsyncSession,
) -> None:
    """行状态防御：召回命中但 PG 行已驳回（物化间隙）→ 不出水合。"""
    seeded = await _seed(session)
    with _searching([f"point-{seeded['p_rejected'].id}"]):
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
    with _searching([f"seg-{seg2.id}", f"seg-{seeded['seg'].id}"]):
        result = await search_service.search(session, q="趋势线")
    assert [s.seek_ms for s in result.segments] == [86_000, 5_000]


async def test_scope_passthrough_to_both_legs(session: AsyncSession) -> None:
    """source/kind/point_type 组装成 _Scope 同构透传词面与向量两路。"""
    with _searching([], []) as (lex, vec):
        await search_service.search(
            session, q="支撑", source_id=5, point_type="case", kind="point"
        )
    for mock in (lex, vec):
        scope = mock.await_args.args[-1]
        assert scope.source_id == 5
        assert scope.point_type == "case"
        assert scope.kind == "point"
        assert scope.chapter is None


async def test_chapter_scope_forces_point_leg_and_prefix_defense(
    session: AsyncSession,
) -> None:
    """章节过滤：scope 强制只查卡片（_leg_active），水合层前缀精筛兜 containment 粗筛。"""
    seeded = await _seed(session)
    with _searching(
        [f"point-{seeded['p_concept'].id}"],
    ) as (lex, _vec):
        result = await search_service.search(
            session, q="支撑", chapter_path=["第一章"]
        )
    scope = lex.await_args.args[-1]
    assert scope.chapter == ("第一章",)
    assert search_service._leg_active(search_service._POINT_LEG, scope)
    assert not search_service._leg_active(search_service._SEGMENT_LEG, scope)
    assert not search_service._leg_active(search_service._IMAGE_LEG, scope)
    # p_concept.chapter_path = ["第二章", ...] 不在请求前缀内 → 不出水合
    assert result.points == []


async def test_embedding_unavailable_falls_back_to_lexical(
    session: AsyncSession,
) -> None:
    """embedding 槽位缺失：词面单路继续服务并标记降级，向量路不发起。"""
    seeded = await _seed(session)
    with _searching(
        [f"point-{seeded['p_case'].id}"], query_vec=None
    ) as (_lex, vec):
        result = await search_service.search(session, q="头肩顶")
    assert result.degraded == "embedding_unavailable"
    vec.assert_not_awaited()
    assert [p.id for p in result.points] == [seeded["p_case"].id]


async def test_query_vector_none_on_missing_slot_or_call_failure(
    session: AsyncSession,
) -> None:
    """查询向量的两条失败路径：槽位缺失与嵌入调用异常均返回 None。"""
    embed = MagicMock()
    embed.embed = AsyncMock(side_effect=KbEmbeddingError("gateway 502"))
    with patch.object(
        search_service,
        "build_embedding_client",
        new=AsyncMock(side_effect=UnprocessableEntityError("embedding 未配置")),
    ):
        assert await search_service._query_vector(session, "任意") is None
    with patch.object(
        search_service, "build_embedding_client", new=AsyncMock(return_value=embed)
    ):
        assert await search_service._query_vector(session, "任意") is None
    embed.embed.assert_awaited_once()


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
    with _searching([f"point-{seeded['p_case'].id}"]):
        result = await search_service.search(session, q="头肩顶案例")
    frames = result.points[0].frames
    assert [f.caption for f in frames] == ["头肩顶颈线"]  # 排除帧/窗外帧都不在


async def test_excluded_image_hit_filtered(session: AsyncSession) -> None:
    """图片命中水合排除已排除/未描述行。"""
    seeded = await _seed(session)
    with _searching([], [f"img-{seeded['frame_ex'].id}"]):
        result = await search_service.search(session, q="被排除帧")
    assert result.images == []


def test_escape_like_treats_input_as_literal() -> None:
    r"""用户输入的 %/_/\ 按字面匹配，不注入通配语义。"""
    assert (
        search_service._escape_like("100%_趋势\\A")
        == "100\\%\\_趋势\\\\A"
    )


def test_leg_active_rules() -> None:
    """kind 限定行类；point_type/章节强制卡片单类。"""
    plain = search_service._Scope(None, None, None, None)
    assert all(
        search_service._leg_active(leg, plain)
        for leg in search_service._LEGS
    )
    by_kind = search_service._Scope(None, None, "image", None)
    assert [search_service._leg_active(leg, by_kind) for leg in search_service._LEGS] == [
        False,
        False,
        True,
    ]
    typed = search_service._Scope(None, "case", None, None)
    assert [search_service._leg_active(leg, typed) for leg in search_service._LEGS] == [
        True,
        False,
        False,
    ]


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
