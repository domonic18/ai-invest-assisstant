"""知识点审核服务单测：章节发布、列表计数、白名单修订、通过/驳回/合并/新增。"""

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.constants.kb import KbPointStatus
from app.core.database import Base
from app.core.exceptions import ConflictError, NotFoundError
from app.models.account_quota import AdminAuditLog
from app.models.kb import KbKnowledgePoint, KbMedia, KbSource
from app.schemas.kb import (
    KbChapterNode,
    KbChaptersPublishRequest,
    KbPointCreateRequest,
    KbPointPatchRequest,
    KbPointRejectRequest,
    KbPointsMergeRequest,
)
from app.services.kb import review_service

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
                KbKnowledgePoint.__table__,
                AdminAuditLog.__table__,
            ],
        )
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as db:
        yield db
    await engine.dispose()


async def _seed_source(db: AsyncSession) -> KbSource:
    src = KbSource(source_type="course", name="课")
    db.add(src)
    await db.commit()
    return src


async def _get_or_create_media(db: AsyncSession, source: KbSource) -> KbMedia:
    """同源复用一条素材（kb_media (source_id, episode_no) 唯一）。"""
    media = (
        await db.execute(
            select(KbMedia).where(KbMedia.source_id == source.id).limit(1)
        )
    ).scalar_one_or_none()
    if media is None:
        media = KbMedia(
            source_id=source.id,
            media_kind="video",
            episode_no=1,
            title="第 1 集",
            file_name="e1.mp4",
            cos_key=f"kb/{source.id}/1/e1.mp4",
            file_size=10,
            file_hash="b" * 32,
            process_status="done",
        )
        db.add(media)
        await db.flush()
    return media


async def _seed_point(
    db: AsyncSession,
    source: KbSource,
    *,
    status: str = "draft",
    title: str = "复利",
    related_ids: list[int] | None = None,
) -> KbKnowledgePoint:
    media = await _get_or_create_media(db, source)
    row = KbKnowledgePoint(
        source_id=source.id,
        media_id=media.id,
        point_type="concept",
        title=title,
        body="正文",
        excerpt="摘抄",
        related_ids=related_ids or [],
        chapter_path=[],
        status=status,
        embedding_dirty=False,
    )
    db.add(row)
    await db.commit()
    return row


# ---------------------------------------------------------------------------
# 章节树
# ---------------------------------------------------------------------------


async def test_publish_chapters_writes_draft_and_published(session: AsyncSession) -> None:
    src = await _seed_source(session)
    payload = KbChaptersPublishRequest(
        chapters=[
            KbChapterNode(id="1", title="价值篇", children=[KbChapterNode(id="1.1", title="复利", children=[])])
        ]
    )
    out = await review_service.publish_chapters(session, src.id, payload, actor_id=1)

    assert out.draft is not None and out.published is not None
    assert out.draft[0].title == "价值篇"
    row = await session.get(KbSource, src.id)
    assert row.chapter_tree["published"][0]["children"][0]["id"] == "1.1"
    audits = (await session.execute(select(AdminAuditLog))).scalars().all()
    assert [a.action for a in audits] == [review_service.AUDIT_CHAPTERS_PUBLISH]


async def test_publish_rejects_duplicate_ids_and_blank_titles(session: AsyncSession) -> None:
    src = await _seed_source(session)
    dup = KbChaptersPublishRequest(
        chapters=[
            KbChapterNode(id="1", title="A", children=[]),
            KbChapterNode(id="1", title="B", children=[]),
        ]
    )
    with pytest.raises(Exception, match="重复"):
        await review_service.publish_chapters(session, src.id, dup, actor_id=1)
    blank = KbChaptersPublishRequest(
        chapters=[KbChapterNode(id="x", title="  ", children=[])]
    )
    with pytest.raises(Exception, match="标题不能为空"):
        await review_service.publish_chapters(session, src.id, blank, actor_id=1)


# ---------------------------------------------------------------------------
# 知识点
# ---------------------------------------------------------------------------


async def test_list_points_counts_and_filter(session: AsyncSession) -> None:
    src = await _seed_source(session)
    await _seed_point(session, src, status="draft", title="A")
    await _seed_point(session, src, status="draft", title="B")
    await _seed_point(session, src, status="published", title="C")
    rejected = await _seed_point(session, src, status="rejected", title="D")
    rejected.needs_review = True
    await session.commit()

    out = await review_service.list_points(session, src.id)
    assert out.total == 4
    assert out.counts.draft == 2
    assert out.counts.published == 1
    assert out.counts.rejected == 1
    assert out.counts.needs_review == 1
    assert out.items[0].episode_no == 1
    assert out.items[0].media_title == "第 1 集"

    only_pub = await review_service.list_points(session, src.id, status="published")
    assert only_pub.total == 1
    assert only_pub.items[0].title == "C"
    assert all(p.status == KbPointStatus.PUBLISHED for p in only_pub.items)


async def test_patch_point_whitelist_and_positioning_forbidden(session: AsyncSession) -> None:
    src = await _seed_source(session)
    row = await _seed_point(session, src)

    patch = KbPointPatchRequest(title="复利效应", chapter_path=["价值篇", "复利"])
    out = await review_service.patch_point(session, row.id, patch, actor_id=1)
    assert out.title == "复利效应"
    assert out.chapter_path == ["价值篇", "复利"]

    # excerpt/时间码是溯源锚点：schema extra=forbid 显式拒绝
    with pytest.raises(ValidationError):
        KbPointPatchRequest.model_validate(
            {"title": "x", "excerpt": "试图改摘抄", "startMs": 1, "endMs": 2}
        )


async def test_approve_sets_embedding_dirty(session: AsyncSession) -> None:
    src = await _seed_source(session)
    row = await _seed_point(session, src)

    out = await review_service.approve_point(session, row.id, actor_id=7)
    assert out.status == KbPointStatus.PUBLISHED
    assert out.needs_review is False
    stored = await session.get(KbKnowledgePoint, row.id)
    assert stored.embedding_dirty is True
    assert stored.reviewed_by == 7
    assert stored.reviewed_at is not None
    audits = (await session.execute(select(AdminAuditLog))).scalars().all()
    assert audits[0].action == review_service.AUDIT_POINT_APPROVE
    assert audits[0].detail["fromStatus"] == KbPointStatus.DRAFT

    # 重复通过：幂等不重复置审计
    n = len((await session.execute(select(AdminAuditLog))).scalars().all())
    await review_service.approve_point(session, row.id, actor_id=7)
    assert len((await session.execute(select(AdminAuditLog))).scalars().all()) == n


async def test_reject_records_reason_and_dirty_only_for_published(session: AsyncSession) -> None:
    src = await _seed_source(session)
    pub = await _seed_point(session, src, status="published", title="P")
    dr = await _seed_point(session, src, status="draft", title="D")

    out = await review_service.reject_point(
        session, pub.id, KbPointRejectRequest(reason="口径错误"), actor_id=1
    )
    assert out.status == KbPointStatus.REJECTED
    assert out.review_note == "口径错误"
    stored = await session.get(KbKnowledgePoint, pub.id)
    assert stored.embedding_dirty is True  # 原 published 置脏（批次 E 删索引）

    out2 = await review_service.reject_point(
        session, dr.id, KbPointRejectRequest(reason="重复"), actor_id=1
    )
    stored2 = await session.get(KbKnowledgePoint, dr.id)
    assert out2.review_note == "重复"
    assert stored2.embedding_dirty is False


async def test_merge_points_unions_related_and_deletes_sources(session: AsyncSession) -> None:
    src = await _seed_source(session)
    target = await _seed_point(session, src, title="目标", related_ids=[99])
    s1 = await _seed_point(session, src, title="重复一", related_ids=[88])
    s2 = await _seed_point(session, src, title="重复二", related_ids=[])

    out = await review_service.merge_points(
        session,
        KbPointsMergeRequest(target_id=target.id, source_ids=[s1.id, s2.id, target.id]),
        actor_id=1,
    )
    assert out.id == target.id
    assert 99 in out.related_ids and 88 in out.related_ids
    assert s1.id not in out.related_ids
    left = (await session.execute(select(KbKnowledgePoint))).scalars().all()
    assert {p.id for p in left} == {target.id}
    audits = (await session.execute(select(AdminAuditLog))).scalars().all()
    assert audits[0].action == review_service.AUDIT_POINT_MERGE


async def test_merge_rejects_cross_source_and_non_draft(session: AsyncSession) -> None:
    src = await _seed_source(session)
    other = await _seed_source(session)
    target = await _seed_point(session, src, title="目标")
    cross = await _seed_point(session, other, title="外库")
    pub = await _seed_point(session, src, status="published", title="已发布")

    with pytest.raises(ConflictError):
        await review_service.merge_points(
            session,
            KbPointsMergeRequest(target_id=target.id, source_ids=[cross.id]),
            actor_id=1,
        )
    with pytest.raises(ConflictError):
        await review_service.merge_points(
            session,
            KbPointsMergeRequest(target_id=target.id, source_ids=[pub.id]),
            actor_id=1,
        )


async def test_create_point_defaults_excerpt_and_draft(session: AsyncSession) -> None:
    src = await _seed_source(session)
    media = await _get_or_create_media(session, src)

    out = await review_service.create_point(
        session,
        KbPointCreateRequest(
            media_id=media.id, point_type="method", title="现金流折现",
            body="用未来现金流折现估值，正文超过两百字也不影响 excerpt 截断默认值。",
        ),
        actor_id=1,
    )
    assert out.status == KbPointStatus.DRAFT
    assert out.excerpt == out.body[:200]
    assert out.episode_no == 1
    audits = (await session.execute(select(AdminAuditLog))).scalars().all()
    assert audits[0].action == review_service.AUDIT_POINT_CREATE

    with pytest.raises(NotFoundError):
        await review_service.create_point(
            session,
            KbPointCreateRequest(
                media_id=99999, point_type="method", title="t", body="b"
            ),
            actor_id=1,
        )
