"""文稿编辑服务单测：读取、按 seqNo 覆盖、脏传播、归属与边界。"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.core.exceptions import ConflictError, NotFoundError, UnprocessableEntityError
from app.models.account_quota import AdminAuditLog
from app.models.kb import KbKnowledgePoint, KbMedia, KbSource, KbTranscriptSegment
from app.schemas.kb import (
    KbSourceCreateRequest,
    KbTranscriptSegmentUpdate,
    KbTranscriptUpdateRequest,
)
from app.services.kb import source_service, transcript_service

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
                AdminAuditLog.__table__,
            ],
        )
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as db:
        yield db
    await engine.dispose()


async def _seed_done_media_with_segments(
    session: AsyncSession, *, source_id: int | None = None
) -> tuple[KbSource, KbMedia]:
    src = await source_service.create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    if source_id is not None and source_id != src.id:
        other = await source_service.create_source(
            session,
            KbSourceCreateRequest(sourceType="course", name="其他课"),
            actor_id=1,
        )
        src = other
    media = KbMedia(
        source_id=src.id,
        media_kind="video",
        episode_no=1,
        title="第 1 集",
        file_name="e1.mp4",
        cos_key=f"kb/{src.id}/1/e1.mp4",
        file_size=100,
        file_hash="c" * 32,
        duration_seconds=60,
        process_status="done",
    )
    session.add(media)
    await session.flush()
    for seq, text in enumerate(["句壹", "句贰", "句叁"], start=1):
        session.add(
            KbTranscriptSegment(
                media_id=media.id,
                source_id=src.id,
                seq_no=seq,
                text=text,
                start_ms=(seq - 1) * 10000,
                end_ms=seq * 10000,
                embedding_dirty=False,
            )
        )
    await session.commit()
    return src, media


async def _segments(session: AsyncSession, media_id: int) -> list[KbTranscriptSegment]:
    rows = await session.execute(
        select(KbTranscriptSegment)
        .where(KbTranscriptSegment.media_id == media_id)
        .order_by(KbTranscriptSegment.seq_no)
    )
    return list(rows.scalars().all())


async def test_get_returns_segments_in_order(session: AsyncSession) -> None:
    src, media = await _seed_done_media_with_segments(session)
    resp = await transcript_service.get_transcript(session, src.id, media.id)
    assert resp.media_id == media.id
    assert [s.seq_no for s in resp.segments] == [1, 2, 3]
    assert [s.text for s in resp.segments] == ["句壹", "句贰", "句叁"]
    assert resp.segments[0].start_ms == 0 and resp.segments[0].end_ms == 10000
    assert resp.edited_at is None


async def test_get_rejects_foreign_source(session: AsyncSession) -> None:
    _, media = await _seed_done_media_with_segments(session)
    with pytest.raises(NotFoundError, match="不属于"):
        await transcript_service.get_transcript(session, 9999, media.id)


async def test_save_only_updates_changed_and_marks_dirty(
    session: AsyncSession,
) -> None:
    src, media = await _seed_done_media_with_segments(session)
    req = KbTranscriptUpdateRequest(
        segments=[
            KbTranscriptSegmentUpdate(seqNo=1, text="句壹"),  # 未变
            KbTranscriptSegmentUpdate(seqNo=2, text="句贰（校正）"),
            KbTranscriptSegmentUpdate(seqNo=3, text="句叁"),  # 未变
        ]
    )
    resp = await transcript_service.save_transcript(
        session, src.id, media.id, req, actor_id=1
    )
    assert resp.updated_count == 1
    assert resp.edited_at is not None
    rows = await _segments(session, media.id)
    assert rows[1].text == "句贰（校正）"
    assert [r.embedding_dirty for r in rows] == [False, True, False]

    actions = (
        (await session.execute(select(AdminAuditLog.action))).scalars().all()
    )
    assert actions[-1] == "kb.transcript.save"


async def test_save_without_change_keeps_edited_at(session: AsyncSession) -> None:
    src, media = await _seed_done_media_with_segments(session)
    req = KbTranscriptUpdateRequest(
        segments=[KbTranscriptSegmentUpdate(seqNo=s, text=t) for s, t in
                  [(1, "句壹"), (2, "句贰"), (3, "句叁")]]
    )
    resp = await transcript_service.save_transcript(
        session, src.id, media.id, req, actor_id=1
    )
    assert resp.updated_count == 0
    assert resp.edited_at is None
    rows = await _segments(session, media.id)
    assert not any(r.embedding_dirty for r in rows)


async def test_save_rejects_unknown_and_duplicate_seq(
    session: AsyncSession,
) -> None:
    src, media = await _seed_done_media_with_segments(session)
    unknown = KbTranscriptUpdateRequest(
        segments=[KbTranscriptSegmentUpdate(seqNo=9, text="x")]
    )
    with pytest.raises(NotFoundError, match="分段 9"):
        await transcript_service.save_transcript(
            session, src.id, media.id, unknown, actor_id=1
        )

    dup = KbTranscriptUpdateRequest(
        segments=[
            KbTranscriptSegmentUpdate(seqNo=1, text="a"),
            KbTranscriptSegmentUpdate(seqNo=1, text="b"),
        ]
    )
    with pytest.raises(UnprocessableEntityError, match="重复"):
        await transcript_service.save_transcript(
            session, src.id, media.id, dup, actor_id=1
        )


async def test_save_rejects_media_without_transcript(
    session: AsyncSession,
) -> None:
    src = await source_service.create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    media = KbMedia(
        source_id=src.id,
        media_kind="video",
        episode_no=1,
        title="第 1 集",
        file_name="e1.mp4",
        cos_key=f"kb/{src.id}/1/e1.mp4",
        file_size=100,
        file_hash="d" * 32,
        process_status="processing",
    )
    session.add(media)
    await session.commit()
    req = KbTranscriptUpdateRequest(
        segments=[KbTranscriptSegmentUpdate(seqNo=1, text="x")]
    )
    with pytest.raises(ConflictError, match="暂无文稿"):
        await transcript_service.save_transcript(
            session, src.id, media.id, req, actor_id=1
        )
