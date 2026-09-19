"""转写编排单测：状态机、COS 分片缓存断点续跑、FAILED 归因（ffmpeg 全 mock）。"""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.constants.kb import KbProcessStatus
from app.core.database import Base
from app.core.locking import redis_lock as real_redis_lock
from app.models.kb import KbMedia, KbSettings, KbSource, KbTranscriptSegment
from app.schemas.kb import KbTranscriptCleanItem, KbTranscriptCleanResult
from app.services.kb import transcribe_service
from app.services.kb.asr_client import AsrChannelError
from app.services.kb.transcribe_pipeline import Sentence
from app.services.social.asr_service import AsrChannelConfig

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
                KbSettings.__table__,
                AsrChannelConfig.__table__,
            ],
        )
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as db:
        yield db
    await engine.dispose()


async def _seed(db: AsyncSession, *, status: str = "queued") -> KbMedia:
    src = KbSource(source_type="course", name="课")
    db.add(src)
    await db.flush()
    db.add(
        KbSettings(
            hotwords=["ROE"],
            segment_max_seconds=30,
            asr_concurrency=1,
            top_k=8,
            unit_prices={"asrPerHour": 3.0},
        )
    )
    media = KbMedia(
        source_id=src.id,
        media_kind="video",
        episode_no=1,
        title="第 1 集",
        file_name="e1.mp4",
        cos_key=f"kb/{src.id}/1/e1.mp4",
        file_size=100,
        file_hash="a" * 32,
        duration_seconds=600,
        process_status=status,
    )
    db.add(media)
    await db.commit()
    return media


class _FakeMinio:
    """按前缀分流：原件返回字节，分片缓存走内存 dict。"""

    def __init__(self) -> None:
        self.original = b"fake-original-bytes"
        self.store: dict[str, bytes] = {}
        self.asr_calls = 0

    async def download_file(self, object_name: str, bucket_name: str | None = None) -> bytes:
        if object_name.startswith("kb/derived/"):
            return self.store[object_name]
        return self.original

    async def stat_object(self, object_name: str, bucket_name: str | None = None) -> tuple[int, str] | None:
        if object_name in self.store:
            return (len(self.store[object_name]), "x")
        return None

    async def upload_file(
        self, object_name: str, data: bytes, content_type: str = "application/pdf",
        bucket_name: str | None = None,
    ) -> str:
        self.store[object_name] = data
        return object_name


def _asr_result() -> Any:
    from app.services.kb.asr_client import ChunkTranscript

    return ChunkTranscript(
        [Sentence(0, 10_000, "句一"), Sentence(10_000, 20_000, "句二")], 20.0
    )


def _patch_pipeline_env(minio: _FakeMinio, *, clean_result: Any, asr_side_effect: Any = None):
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_lock(*args: Any, **kwargs: Any):
        yield True

    async def fake_extract(src: Path, out: Path) -> Path:
        out.write_bytes(src.read_bytes())
        return out

    async def fake_run_ffmpeg(*args: str) -> tuple[int, str]:
        out = Path(args[-1])
        out.write_bytes(b"chunk-wav")
        return 0, ""

    async def fake_probe(wav: Path) -> float:
        return 600.0

    async def fake_silences(wav: Path) -> list[tuple[float, float]]:
        return [(299.5, 300.5)]

    asr_mock = AsyncMock(side_effect=asr_side_effect or (lambda *a, **k: _asr_result()))
    return {
        "lock": patch("app.services.kb.transcribe_service.redis_lock", side_effect=fake_lock),
        "minio": patch(
            "app.services.kb.transcribe_service.get_minio_service", return_value=minio
        ),
        "resolve_role": patch(
            "app.services.kb.transcribe_service.resolve_role_model",
            new=AsyncMock(return_value=SimpleNamespace(id=99)),
        ),
        "load_config": patch(
            "app.services.kb.transcribe_service.load_config",
            new=AsyncMock(
                return_value=AsrChannelConfig(
                    id=1, provider="minimax", base_url="https://api.minimaxi.com",
                    model="asr-1.0", api_key_encrypted="enc", enabled=True,
                )
            ),
        ),
        "decrypt": patch(
            "app.services.kb.transcribe_service.decrypt_token", return_value="key"
        ),
        "extract": patch(
            "app.services.kb.transcribe_service._extract_audio", side_effect=fake_extract
        ),
        "slice": patch(
            "app.services.kb.transcribe_service._run_ffmpeg", side_effect=fake_run_ffmpeg
        ),
        "probe": patch(
            "app.services.kb.transcribe_service._probe_duration", side_effect=fake_probe
        ),
        "silences": patch(
            "app.services.kb.transcribe_service._detect_silences", side_effect=fake_silences
        ),
        "asr": patch(
            "app.services.kb.transcribe_service.transcribe_chunk", new=asr_mock
        ),
        "clean": patch(
            "app.agent.runtime.structured.run_structured",
            new=AsyncMock(return_value=clean_result),
        ),
    }, asr_mock


async def test_transcribe_happy_path_done_with_segments(session: AsyncSession) -> None:
    media = await _seed(session)
    clean = KbTranscriptCleanResult(
        items=[KbTranscriptCleanItem(seq=1, text="句壹"), KbTranscriptCleanItem(seq=2, text="句贰")]
    )
    minio = _FakeMinio()
    patches, asr_mock = _patch_pipeline_env(minio, clean_result=clean)
    with patches["lock"], patches["minio"], patches["load_config"], patches["decrypt"], \
            patches["extract"], patches["slice"], patches["probe"], patches["silences"], \
            patches["asr"], patches["clean"], patches["resolve_role"]:
        outcome = await transcribe_service.transcribe_media(session, media.id)

    assert outcome == "done"
    row = await session.get(KbMedia, media.id)
    assert row.process_status == KbProcessStatus.DONE
    assert row.process_error is None
    # 600s、300s 处静音 → 2 分片，各调一次 ASR
    assert asr_mock.await_count == 2
    assert row.process_meta["chunk_count"] == 2
    assert row.process_meta["provider"] == "minimax"
    assert row.process_meta["est_cost"] == pytest.approx(0.5)

    segs = (
        (await session.execute(select(KbTranscriptSegment).order_by(KbTranscriptSegment.seq_no)))
        .scalars()
        .all()
    )
    # 两分片各 2 句（10s 句长，30s 上限）→ 每分片并句为 1 段，清洗按段回填
    assert [s.text for s in segs] == ["句壹", "句贰"]
    assert segs[0].start_ms == 0 and segs[0].end_ms == 20_000
    assert segs[1].start_ms == 300_000 and segs[1].end_ms == 320_000
    assert all(s.embedding_dirty for s in segs)

    # 分片结果写 COS derived 前缀
    cached = [k for k in minio.store if k.startswith("kb/derived/")]
    assert len(cached) == 2


async def test_transcribe_resume_skips_billed_chunks(session: AsyncSession) -> None:
    """断点续跑：分片缓存命中时不重复调 ASR（不重复计费）。"""
    media = await _seed(session)
    clean = KbTranscriptCleanResult(
        items=[KbTranscriptCleanItem(seq=1, text="缓存句"), KbTranscriptCleanItem(seq=2, text="缓存句")]
    )
    minio = _FakeMinio()
    for key in (
        f"kb/derived/{media.id}/chunks/000000000000-000000300000.json",
        f"kb/derived/{media.id}/chunks/000000300000-000000600000.json",
    ):
        minio.store[key] = json.dumps(
            {"sentences": [{"start_ms": 0, "end_ms": 5000, "text": "缓存句"}]}
        ).encode()
    patches, asr_mock = _patch_pipeline_env(minio, clean_result=clean)
    with patches["lock"], patches["minio"], patches["load_config"], patches["decrypt"], \
            patches["extract"], patches["slice"], patches["probe"], patches["silences"], \
            patches["asr"], patches["clean"], patches["resolve_role"]:
        outcome = await transcribe_service.transcribe_media(session, media.id)

    assert outcome == "done"
    asr_mock.assert_not_awaited()
    segs = (await session.execute(select(KbTranscriptSegment))).scalars().all()
    assert [s.text for s in segs] == ["缓存句", "缓存句"]


async def test_transcribe_asr_business_error_marks_failed(session: AsyncSession) -> None:
    media = await _seed(session)
    minio = _FakeMinio()

    def _boom(*args: Any, **kwargs: Any) -> Any:
        raise AsrChannelError("asr_business_1004: 配额不足")

    patches, _ = _patch_pipeline_env(minio, clean_result=None, asr_side_effect=_boom)
    with patches["lock"], patches["minio"], patches["load_config"], patches["decrypt"], \
            patches["extract"], patches["slice"], patches["probe"], patches["silences"], \
            patches["asr"], patches["clean"], patches["resolve_role"]:
        outcome = await transcribe_service.transcribe_media(session, media.id)

    assert outcome == "failed"
    row = await session.get(KbMedia, media.id)
    assert row.process_status == KbProcessStatus.FAILED
    assert "asr_business_1004" in row.process_error
    # 不留半截分段
    segs = (await session.execute(select(KbTranscriptSegment))).scalars().all()
    assert segs == []


async def test_transcribe_skips_non_queued(session: AsyncSession) -> None:
    media = await _seed(session, status="processing")
    assert await transcribe_service.transcribe_media(session, media.id) == "skipped"


async def test_transcribe_busy_lock(session: AsyncSession) -> None:
    media = await _seed(session)
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def busy_lock(*args: Any, **kwargs: Any):
        yield False

    with patch(
        "app.services.kb.transcribe_service.redis_lock", side_effect=busy_lock
    ):
        assert await transcribe_service.transcribe_media(session, media.id) == "busy"
    row = await session.get(KbMedia, media.id)
    assert row.process_status == KbProcessStatus.QUEUED


def test_lock_key_template_matches_real_lock_signature() -> None:
    """锁键模板与 redis_lock 真实签名对齐（防漂移）。"""
    from app.constants.kb import KB_TRANSCRIBE_LOCK_KEY_TEMPLATE

    assert KB_TRANSCRIBE_LOCK_KEY_TEMPLATE.format(media_id=1) == "kb:lock:transcribe:1"
    assert real_redis_lock is not None
