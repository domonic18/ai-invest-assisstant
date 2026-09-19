"""课程转写编排（arch/12 §4）：queued → processing → done / failed。

分片链路：ffmpeg 16kHz 单声道 wav → silencedetect 切分（≤480s）→ 逐片
asr-1.0（并发 = ``asr_concurrency``，分片结果缓存 COS derived 前缀支持
断点续跑、不重复计费）→ 句级合并 → ≤segment_max_seconds 切句 → 清洗
（``clean_model_id`` 角色槽位 + 热词入 prompt）→ 分段落库。

失败显式 FAILED 归因写 ``process_error``（渠道不可用/超限不静默重试）。
用量：清洗经 ``run_structured`` 自动计量（feature=kb_clean，system 维度）。
"""

import asyncio
import json
import tempfile
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.kb import (
    KB_TRANSCRIBE_LOCK_KEY_TEMPLATE,
    KbProcessStatus,
)
from app.core.clock import utc_now
from app.core.locking import redis_lock
from app.models.kb import KbMedia, KbTranscriptSegment
from app.repositories.kb import media_repository
from app.services.common.minio_service import get_minio_service
from app.services.kb import transcribe_pipeline as pipeline
from app.services.kb.asr_client import (
    AsrChannelError,
    AsrEmptyResultError,
    ChunkTranscript,
    transcribe_chunk,
)
from app.services.kb.settings_service import get_settings_row, resolve_role_model
from app.services.kb.transcribe_pipeline import Sentence
from app.services.quota.constants import FEATURE_KB_CLEAN
from app.services.quota.context import meter_scope
from app.services.social.asr_service import load_config
from app.utils.crypto import decrypt_token

logger = structlog.get_logger(__name__)

_LOCK_TTL_SECONDS = 4200
_CLEAN_BATCH_SENTENCES = 40
_SEGMENTS_COMMIT_BATCH = 50
_ERROR_MAX_LEN = 1000
_SILENCE_FILTER = "silencedetect=noise=-30dB:d=0.5"
#: 渠道偶发空返回（观测 HTTP 200 无 text）重试一次的退避
_ASR_EMPTY_RETRY_SECONDS = 3.0


class TranscribeError(Exception):
    """转写管线本机环节失败（ffmpeg 缺失/失败、素材不可读）。"""


async def process_queued(session: AsyncSession, *, limit: int = 10) -> int:
    """消化 queued 素材（单素材互斥锁，忙素材跳过）。返回本轮完成数。"""
    rows = await media_repository.list_queued_media(session)
    done = 0
    for row in rows[:limit]:
        outcome = await transcribe_media(session, row.id)
        if outcome in ("done", "failed"):
            done += 1
    return done


async def transcribe_media(session: AsyncSession, media_id: int) -> str:
    """转写单集素材，返回终态（done/failed/busy/skipped）。

    Raises:
        不会向上抛——所有失败归因为素材 FAILED 状态（定时路径需要）。
    """
    row = await media_repository.get(session, media_id)
    if (
        row is None
        or row.deleted_at is not None
        or row.process_status != KbProcessStatus.QUEUED
    ):
        return "skipped"
    async with redis_lock(
        KB_TRANSCRIBE_LOCK_KEY_TEMPLATE.format(media_id=media_id),
        ttl=_LOCK_TTL_SECONDS,
        blocking=False,
    ) as acquired:
        if not acquired:
            logger.info("kb_transcribe_busy", media_id=media_id)
            return "busy"
        row = await media_repository.get(session, media_id)
        if (
            row is None
            or row.deleted_at is not None
            or row.process_status != KbProcessStatus.QUEUED
        ):
            return "skipped"
        try:
            await _run(session, row)
            return "done"
        except (TranscribeError, AsrChannelError) as exc:
            await _mark_failed(session, media_id, str(exc))
            return "failed"
        except Exception as exc:  # noqa: BLE001 —— 定时路径兜底归因
            logger.exception("kb_transcribe_unexpected", media_id=media_id)
            await _mark_failed(session, media_id, f"unexpected: {exc}")
            return "failed"


async def _run(session: AsyncSession, row: KbMedia) -> None:
    """主链路：状态 processing → 分片转写 → 清洗 → 落库 → done。"""
    config = await load_config(session)
    if config is None or not config.enabled or not config.api_key_encrypted:
        raise TranscribeError("asr_not_configured")
    try:
        api_key = decrypt_token(config.api_key_encrypted)
    except Exception as exc:  # noqa: BLE001
        raise TranscribeError("asr_key_invalid") from exc
    settings = await get_settings_row(session)
    prices = settings.unit_prices or {}
    asr_per_hour = Decimal(str(prices.get("asrPerHour") or 0))

    row.process_status = KbProcessStatus.PROCESSING
    row.process_error = None
    await session.commit()

    minio = get_minio_service()
    original = await minio.download_file(row.cos_key)
    chunk_results = await _transcribe_all_chunks(
        minio, row, original, config, api_key, settings.asr_concurrency or 1
    )

    merged = pipeline.merge_chunks(chunk_results)
    segments = pipeline.group_sentences(
        merged, max_seconds=float(settings.segment_max_seconds)
    )
    segments = await _clean_segments(session, segments, list(settings.hotwords or []))

    await media_repository.delete_segments(session, row.id)
    audio_seconds = sum(
        c.end_seconds - c.start_seconds for c in chunk_results
    )
    est_cost = (Decimal(str(audio_seconds)) / Decimal("3600") * asr_per_hour).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )
    for i, seg in enumerate(segments, start=1):
        session.add(
            KbTranscriptSegment(
                source_id=row.source_id,
                media_id=row.id,
                seq_no=i,
                text=seg.text,
                start_ms=seg.start_ms,
                end_ms=seg.end_ms,
            )
        )
        if i % _SEGMENTS_COMMIT_BATCH == 0:
            await session.commit()
    row.process_status = KbProcessStatus.DONE
    row.extracted_at = utc_now()
    row.process_meta = {
        **(row.process_meta or {}),
        "provider": config.provider,
        "model": config.model,
        "audio_seconds": round(audio_seconds, 1),
        "chunk_count": len(chunk_results),
        "empty_chunks": sum(1 for c in chunk_results if not c.sentences),
        "segment_count": len(segments),
        "est_cost": float(est_cost),
    }
    await session.commit()
    logger.info(
        "kb_transcribe_done",
        media_id=row.id,
        segments=len(segments),
        chunks=len(chunk_results),
    )


async def _transcribe_all_chunks(
    minio: Any,
    row: KbMedia,
    original: bytes,
    config: Any,
    api_key: str,
    concurrency: int,
) -> list[pipeline.ChunkAsr]:
    """ffmpeg 抽音轨 + 切分 + 并发转写（COS 分片缓存命中不计费）。"""
    with tempfile.TemporaryDirectory(prefix="kb-asr-") as tmp:
        tmp_dir = Path(tmp)
        src = tmp_dir / "input"
        src.write_bytes(original)
        wav = await _extract_audio(src, tmp_dir / "audio.wav")
        duration = await _probe_duration(wav)
        silences = await _detect_silences(wav)
        chunks = pipeline.plan_chunks(duration, silences)
        if not chunks:
            raise TranscribeError("audio_empty")

        semaphore = asyncio.Semaphore(concurrency)

        async def one(start: float, end: float) -> pipeline.ChunkAsr:
            async with semaphore:
                sentences = await _chunk_sentences(
                    minio, row.id, wav, start, end, config, api_key
                )
            return pipeline.ChunkAsr(
                start_seconds=start, end_seconds=end, sentences=sentences
            )

        return list(
            await asyncio.gather(*(one(s, e) for s, e in chunks))
        )


async def _chunk_sentences(
    minio: Any,
    media_id: int,
    wav: Path,
    start: float,
    end: float,
    config: Any,
    api_key: str,
) -> list[Sentence]:
    """单分片：COS 缓存命中直接回放，否则转写并写缓存。"""
    key = (
        f"kb/derived/{media_id}/chunks/"
        f"{int(start * 1000):012d}-{int(end * 1000):012d}.json"
    )
    cached = await minio.stat_object(key)
    if cached is not None:
        payload = json.loads((await minio.download_file(key)).decode("utf-8"))
        return [
            Sentence(s["start_ms"], s["end_ms"], s["text"])
            for s in payload.get("sentences", [])
        ]

    with tempfile.TemporaryDirectory(prefix="kb-chunk-") as tmp:
        chunk_path = Path(tmp) / "chunk.wav"
        await _run_ffmpeg(
            "ffmpeg", "-y", "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
            "-i", str(wav), "-c:a", "pcm_s16le", str(chunk_path),
        )
        wav_bytes = chunk_path.read_bytes()

    transcript = await _transcribe_with_retry(config, api_key, wav_bytes, chunk_path.name)
    if not transcript.sentences:
        # 降级空结果不写缓存：渠道恢复后重跑该分片可拿回内容
        return []
    payload = {
        "sentences": [
            {"start_ms": s.start_ms, "end_ms": s.end_ms, "text": s.text}
            for s in transcript.sentences
        ]
    }
    await minio.upload_file(
        key,
        json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        content_type="application/json",
    )
    return transcript.sentences


async def _transcribe_with_retry(
    config: Any, api_key: str, wav_bytes: bytes, filename: str
) -> ChunkTranscript:
    """单分片转写：偶发空返回退避重试一次，仍空降级为空句（不拖垮整集）。

    其余渠道错误（HTTP/业务错误）照旧向上抛，由 transcribe_media 归因 FAILED。
    """
    try:
        return await transcribe_chunk(config, api_key, wav_bytes, filename=filename)
    except AsrEmptyResultError:
        logger.warning("kb_asr_chunk_empty_retry", filename=filename)
    await asyncio.sleep(_ASR_EMPTY_RETRY_SECONDS)
    try:
        return await transcribe_chunk(config, api_key, wav_bytes, filename=filename)
    except AsrEmptyResultError:
        logger.warning("kb_asr_chunk_empty_skipped", filename=filename)
        return ChunkTranscript([])


async def _clean_segments(
    session: AsyncSession, segments: list[Sentence], hotwords: list[str]
) -> list[Sentence]:
    """LLM 清洗：只改错字/术语/语气词，seq 对应回填，不改时间轴。"""
    if not segments:
        return segments
    from app.agent.runtime.structured import run_structured
    from app.schemas.kb import KbTranscriptCleanResult

    config = await resolve_role_model(session, "clean")
    cleaned: list[Sentence] = []
    for offset in range(0, len(segments), _CLEAN_BATCH_SENTENCES):
        batch = segments[offset : offset + _CLEAN_BATCH_SENTENCES]
        numbered = "\n".join(
            f"{i}. {seg.text}" for i, seg in enumerate(batch, start=1)
        )
        hot = "、".join(hotwords) if hotwords else "（无）"
        prompt = (
            "你是金融课程文稿校对员。逐句修正转写文本中的错别字、术语拼写与"
            "语气词，保持语义与句序不变，不得增删句子。\n"
            f"热词表（优先按此校正术语）：{hot}\n"
            "输入为编号句列表，输出 items 与输入等长且 seq 一一对应。\n\n"
            f"{numbered}"
        )
        with meter_scope(None, FEATURE_KB_CLEAN):
            result = await run_structured(
                session, result_type=KbTranscriptCleanResult, user_prompt=prompt,
                config_id=config.id,
            )
        by_seq = {item.seq: item.text for item in result.items}
        for i, seg in enumerate(batch, start=1):
            text = by_seq.get(i, seg.text).strip()
            cleaned.append(Sentence(seg.start_ms, seg.end_ms, text or seg.text))
    return cleaned


async def _extract_audio(src: Path, out: Path) -> Path:
    """抽 16kHz 单声道 wav。"""
    await _run_ffmpeg(
        "ffmpeg", "-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000",
        "-c:a", "pcm_s16le", str(out),
    )
    return out


async def _detect_silences(wav: Path) -> list[tuple[float, float]]:
    """silencedetect 静音区间（-30dB / 最短 0.5s）。"""
    code, stderr = await _run_ffmpeg(
        "ffmpeg", "-i", str(wav), "-af", _SILENCE_FILTER,
        "-f", "null", "-",
    )
    if code != 0:
        raise TranscribeError("ffmpeg_silencedetect_failed")
    return pipeline.parse_silencedetect(stderr)


async def _probe_duration(wav: Path) -> float:
    """ffprobe 读取时长（秒）。"""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(wav),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
    except FileNotFoundError as exc:
        raise TranscribeError("ffmpeg_unavailable") from exc
    try:
        return float(stdout.decode().strip())
    except ValueError as exc:
        raise TranscribeError("ffmpeg_probe_failed") from exc


async def _run_ffmpeg(*args: str) -> tuple[int, str]:
    """执行 ffmpeg 子进程，返回 (returncode, stderr)。"""
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
    except FileNotFoundError as exc:
        raise TranscribeError("ffmpeg_unavailable") from exc
    return proc.returncode or 0, stderr.decode(errors="replace")


async def _mark_failed(session: AsyncSession, media_id: int, reason: str) -> None:
    """FAILED 归因（渠道失败不重试烧钱；人工排查后可重新入队）。"""
    await session.rollback()
    row = await media_repository.get(session, media_id)
    if row is None:
        return
    row.process_status = KbProcessStatus.FAILED
    row.process_error = reason[:_ERROR_MAX_LEN]
    await session.commit()
    logger.warning("kb_transcribe_failed", media_id=media_id, reason=reason)
