"""费用闸门单测：预估公式、状态门（uploaded 不可直接确认）、审计。"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.constants.kb import KbProcessStatus
from app.core.database import Base
from app.core.exceptions import ConflictError, NotFoundError, UnprocessableEntityError
from app.models.account_quota import AdminAuditLog
from app.models.kb import KbMedia, KbSettings, KbSource
from app.schemas.kb import KbSourceCreateRequest
from app.services.kb import cost_service
from app.services.kb.source_service import create_source

pytestmark = pytest.mark.unit

ASR_PER_HOUR = 3.0  # 每小时 3 元，便于心算验证


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                KbSettings.__table__,
                KbSource.__table__,
                KbMedia.__table__,
                AdminAuditLog.__table__,
            ],
        )
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as db:
        settings = KbSettings(
            hotwords=[],
            segment_max_seconds=30,
            asr_concurrency=2,
            top_k=8,
            unit_prices={"asrPerHour": ASR_PER_HOUR, "vlmPerImage": 0.05},
        )
        db.add(settings)
        await db.commit()
        yield db
    await engine.dispose()


async def _seed_media(
    session: AsyncSession,
    source_id: int,
    *,
    duration_seconds: int | None = 3600,
    status: str = KbProcessStatus.UPLOADED,
    media_kind: str = "video",
) -> KbMedia:
    row = KbMedia(
        source_id=source_id,
        media_kind=media_kind,
        episode_no=1,
        title="第 1 集",
        file_name="e1.mp4",
        cos_key=f"kb/{source_id}/1/e1.mp4",
        file_size=100,
        file_hash="a" * 32,
        duration_seconds=duration_seconds,
        process_status=status,
    )
    session.add(row)
    await session.commit()
    return row


async def test_estimate_computes_asr_and_clean_tokens(
    session: AsyncSession,
) -> None:
    src = await create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    media = await _seed_media(session, src.id, duration_seconds=3600)
    resp = await cost_service.estimate_cost(session, src.id, [media.id])

    assert resp.currency == "CNY"
    assert len(resp.items) == 1
    item = resp.items[0]
    assert item.asr_cost == pytest.approx(ASR_PER_HOUR)
    # 3600s × 4字/s ÷ 1.5字/token = 9600
    assert item.clean_tokens == 9600
    assert item.estimated_cost == pytest.approx(ASR_PER_HOUR)
    assert resp.total == pytest.approx(ASR_PER_HOUR)

    row = await session.get(KbMedia, media.id)
    assert row.process_status == KbProcessStatus.AWAITING_COST


async def test_estimate_requires_price_config(session: AsyncSession) -> None:
    src = await create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    media = await _seed_media(session, src.id)
    row = await session.get(KbSettings, 1)
    row.unit_prices = {}
    await session.commit()
    with pytest.raises(UnprocessableEntityError, match="asrPerHour"):
        await cost_service.estimate_cost(session, src.id, [media.id])


async def test_estimate_rejects_foreign_media(session: AsyncSession) -> None:
    src = await create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    with pytest.raises(NotFoundError):
        await cost_service.estimate_cost(session, src.id, [999])


async def test_estimate_is_idempotent_for_awaiting(session: AsyncSession) -> None:
    src = await create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    media = await _seed_media(
        session, src.id, status=KbProcessStatus.AWAITING_COST
    )
    resp = await cost_service.estimate_cost(session, src.id, [media.id])
    assert resp.items[0].media_id == media.id
    row = await session.get(KbMedia, media.id)
    assert row.process_status == KbProcessStatus.AWAITING_COST


async def test_confirm_moves_awaiting_to_queued_and_audits(
    session: AsyncSession,
) -> None:
    src = await create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    media = await _seed_media(
        session, src.id, status=KbProcessStatus.AWAITING_COST
    )
    queued = await cost_service.confirm_cost(
        session, src.id, [media.id], actor_id=1
    )
    assert queued == [media.id]
    row = await session.get(KbMedia, media.id)
    assert row.process_status == KbProcessStatus.QUEUED
    actions = (
        (await session.execute(select(AdminAuditLog.action))).scalars().all()
    )
    assert actions[-1] == "kb.cost.confirm"


async def test_confirm_rejects_uploaded_gate_not_skippable(
    session: AsyncSession,
) -> None:
    """闸门：uploaded 未经预估不得直接入队。"""
    src = await create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    media = await _seed_media(session, src.id, status=KbProcessStatus.UPLOADED)
    with pytest.raises(ConflictError, match="闸门"):
        await cost_service.confirm_cost(session, src.id, [media.id], actor_id=1)
    row = await session.get(KbMedia, media.id)
    assert row.process_status == KbProcessStatus.UPLOADED


async def test_confirm_is_noop_for_already_queued(session: AsyncSession) -> None:
    src = await create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    media = await _seed_media(session, src.id, status=KbProcessStatus.QUEUED)
    queued = await cost_service.confirm_cost(
        session, src.id, [media.id], actor_id=1
    )
    assert queued == []
    row = await session.get(KbMedia, media.id)
    assert row.process_status == KbProcessStatus.QUEUED


async def test_full_gate_flow_uploaded_to_queued(session: AsyncSession) -> None:
    """全链路：uploaded → estimate → awaiting_cost → confirm → queued。"""
    src = await create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    media = await _seed_media(session, src.id, duration_seconds=1800)
    await cost_service.estimate_cost(session, src.id, [media.id])
    row = await session.get(KbMedia, media.id)
    assert row.process_status == KbProcessStatus.AWAITING_COST
    queued = await cost_service.confirm_cost(
        session, src.id, [media.id], actor_id=1
    )
    assert queued == [media.id]
    row = await session.get(KbMedia, media.id)
    assert row.process_status == KbProcessStatus.QUEUED


async def test_estimate_skips_book_media_cost(session: AsyncSession) -> None:
    src = await create_source(
        session, KbSourceCreateRequest(sourceType="course", name="课"), actor_id=1
    )
    media = await _seed_media(
        session, src.id, media_kind="book", duration_seconds=None
    )
    resp = await cost_service.estimate_cost(session, src.id, [media.id])
    assert resp.items[0].asr_cost == 0
    assert resp.total == 0
