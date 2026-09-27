"""课程视频关键帧：选帧阶段（零 LLM）与视觉通道编排。

选帧（arch/09 §4.1 阶段一）：扫 ``done 且 vision_at 为空`` 的 video 素材 →
下载源文件 → 三路信号选帧（vision_pipeline 纯函数）→ ffmpeg 抽帧 +
aHash 近重复过滤 → 原图/缩略图传 COS derived 前缀 → ``kb_image_asset``
行（pending）→ ``vision_at`` 记账（幂等键，重跑不重抽）。

失败语义：单集选帧失败回滚后独立写 ``process_meta.visionAttempts/
visionError``，累计不再扫；描述阶段见 ``vision_describe``。
"""

import tempfile
from pathlib import Path

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.kb import (
    KB_VISION_FIXED_INTERVAL_SECONDS,
    KB_VISION_LOCK_KEY,
    KB_VISION_MAX_FRAMES_PER_MEDIA,
    KB_VISION_MAX_MEDIA_ATTEMPTS,
    KB_VISION_MERGE_WINDOW_SECONDS,
    KB_VISION_PHASH_HAMMING_THRESHOLD,
    KB_VISION_SCENE_THRESHOLD,
    KB_VISION_SEEK_TOLERANCE_SECONDS,
)
from app.core.clock import utc_now
from app.core.exceptions import UnprocessableEntityError
from app.core.locking import redis_lock
from app.models.kb import KbImageAsset, KbMedia
from app.repositories.kb import media_repository
from app.services.common.minio_service import get_minio_service
from app.services.kb import vision_pipeline as vpipe
from app.services.kb.settings_service import resolve_role_model
from app.services.kb.vision_common import VisionError
from app.services.kb.vision_describe import _describe_frames
from app.utils import ffmpeg
from app.utils.ffmpeg import FFmpegError

logger = structlog.get_logger(__name__)

_FRAME_KEY_TEMPLATE = "kb/derived/{media_id}/frames/{start_ms:012d}{suffix}.jpg"


async def run_vision(session: AsyncSession) -> dict[str, int]:
    """执行一轮视觉通道（选帧 + 描述），返回分类统计（spider 据此判 SKIPPED）。"""
    async with redis_lock(KB_VISION_LOCK_KEY, ttl=3600, blocking=False) as ok:
        if not ok:
            logger.info("kb_vision_skipped_busy")
            return {"skippedBusy": 1}
        try:
            config = await resolve_role_model(session, "vision")
        except UnprocessableEntityError:
            logger.info("kb_vision_no_model_configured")
            return {"noModelConfigured": 1}
        stats = {
            "mediasFramed": 0,
            "framesCreated": 0,
            "failedMedias": 0,
            "framesDescribed": 0,
            "describeFailed": 0,
        }
        stats.update(await _extract_frames(session))
        stats.update(await _describe_frames(session, config))
        logger.info("kb_vision_done", **stats)
        return stats


async def _extract_frames(session: AsyncSession) -> dict[str, int]:
    stats = {"mediasFramed": 0, "framesCreated": 0, "failedMedias": 0}
    medias = (
        (
            await session.execute(
                select(KbMedia).where(
                    KbMedia.deleted_at.is_(None),
                    KbMedia.media_kind == "video",
                    KbMedia.process_status == "done",
                    KbMedia.vision_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    # 失败路径的 rollback 会使 ORM 实例过期——循环前捕获全部所需字段，
    # 迭代内按 id 重取新鲜实例，防 AttributeError 逃出 per-media 容错
    candidates = [(m.id, dict(m.process_meta or {})) for m in medias]
    for media_id, meta in candidates:
        media = await session.get(KbMedia, media_id)
        if media is None:
            continue
        attempts = int(meta.get("visionAttempts") or 0)
        if attempts >= KB_VISION_MAX_MEDIA_ATTEMPTS:
            continue
        try:
            created = await _frame_one_media(session, media)
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            stats["failedMedias"] += 1
            await _record_failure(session, media_id, attempts, exc)
            continue
        media.vision_at = utc_now()
        media.process_meta = {
            k: v for k, v in meta.items() if k not in ("visionAttempts", "visionError")
        }
        stats["mediasFramed"] += 1
        stats["framesCreated"] += created
        await session.commit()
    return stats


async def _frame_one_media(session: AsyncSession, media: KbMedia) -> int:
    """单集选帧：下载 → 三路信号 → 抽帧去重 → COS + 落行。返回新建帧数。"""
    from app.constants.kb import KbMediaKind

    minio = get_minio_service()
    source_bytes = await minio.download_file(media.cos_key)
    segments = await media_repository.list_segments(session, media.id)
    with tempfile.TemporaryDirectory(prefix="kb-vision-") as tmp:
        src = Path(tmp) / "source.mp4"
        src.write_bytes(source_bytes)
        duration = await _probe_duration(src)
        if duration <= 0:
            duration = float(media.duration_seconds or 0)
        else:
            media.duration_seconds = round(duration)  # 探到即回写，预估费用复用
        if duration <= 0:
            raise VisionError("ffmpeg_probe_failed")

        scene_times = await _detect_scenes(src)
        guide_times = vpipe.guide_timestamps(
            [(seg.start_ms, seg.end_ms, seg.text) for seg in segments]
        )
        frames = vpipe.plan_frames(
            scene_times,
            fixed_interval_seconds=KB_VISION_FIXED_INTERVAL_SECONDS,
            duration_seconds=duration,
            guide_times=guide_times,
            merge_window_seconds=KB_VISION_MERGE_WINDOW_SECONDS,
            max_frames=KB_VISION_MAX_FRAMES_PER_MEDIA,
        )

        kept_hashes: list[int] = []
        created = 0
        for frame in frames:
            seek = max(0.0, frame.start_seconds - KB_VISION_SEEK_TOLERANCE_SECONDS)
            phash = await _frame_phash(src, seek)
            if phash is None:
                continue
            if vpipe.is_near_duplicate(phash, kept_hashes,
                                       KB_VISION_PHASH_HAMMING_THRESHOLD):
                continue
            start_ms = int(seek * 1000)
            original = await _extract_jpeg(
                src, seek, scale=960, quality=3, suffix=""
            )
            thumb = await _extract_jpeg(
                src, seek, scale=320, quality=5, suffix="_thumb"
            )
            if original is None or thumb is None:
                continue
            kept_hashes.append(phash)
            session.add(
                KbImageAsset(
                    source_id=media.source_id,
                    media_id=media.id,
                    page_no=None,
                    start_ms=start_ms,
                    end_ms=None,
                    cos_key=_FRAME_KEY_TEMPLATE.format(
                        media_id=media.id, start_ms=start_ms, suffix=""
                    ),
                    thumb_cos_key=_FRAME_KEY_TEMPLATE.format(
                        media_id=media.id, start_ms=start_ms, suffix="_thumb"
                    ),
                    describe_status="pending",
                    describe_attempts=0,
                    embedding_dirty=False,
                )
            )
            await minio.upload_file(
                _FRAME_KEY_TEMPLATE.format(media_id=media.id, start_ms=start_ms,
                                           suffix=""),
                original,
                content_type="image/jpeg",
            )
            await minio.upload_file(
                _FRAME_KEY_TEMPLATE.format(media_id=media.id, start_ms=start_ms,
                                           suffix="_thumb"),
                thumb,
                content_type="image/jpeg",
            )
            created += 1
        logger.info(
            "kb_vision_frames_planned",
            media_id=media.id,
            kind=KbMediaKind.VIDEO.value,
            planned=len(frames),
            created=created,
            scene_hits=len(scene_times),
            guide_hits=len(guide_times),
        )
        return created


async def _detect_scenes(src: Path) -> list[float]:
    """场景切换检测（整片解码，showinfo stderr 解析 pts_time）。

    ``-an/-sn/-dn`` 丢掉非视频流：null muxer 缓冲音轨会以
    ``Too many packets buffered`` 整体失败。
    """
    code, stderr = await _run(
        "ffmpeg", "-i", str(src), "-an", "-sn", "-dn",
        "-vf", f"select='gt(scene,{KB_VISION_SCENE_THRESHOLD})',showinfo",
        "-f", "null", "-",
    )
    if code != 0:
        raise VisionError("ffmpeg_scene_detect_failed")
    return vpipe.parse_scene_times(stderr)


async def _extract_jpeg(
    src: Path, seek: float, *, scale: int, quality: int, suffix: str
) -> bytes | None:
    """按时刻抽一帧 JPEG（输入侧快速 seek + 转码精确取帧）。"""
    out = src.parent / f"frame_{seek:.3f}{suffix}.jpg"
    code, _ = await _run(
        "ffmpeg", "-y", "-ss", f"{seek:.3f}", "-i", str(src),
        "-frames:v", "1", "-vf", f"scale={scale}:-2", "-q:v", str(quality),
        str(out),
    )
    if code != 0 or not out.exists():
        return None
    return out.read_bytes()


async def _frame_phash(src: Path, seek: float) -> int | None:
    """抽 16×16 灰度 rawvideo 计算 aHash（帧缺失返回 None）。"""
    try:
        code, _, stdout = await ffmpeg.run(
            "ffmpeg", "-ss", f"{seek:.3f}", "-i", str(src),
            "-frames:v", "1", "-vf", "scale=16:16",
            "-f", "rawvideo", "-pix_fmt", "gray", "-",
            capture_stdout=True,
        )
    except FFmpegError as exc:
        raise VisionError("ffmpeg_unavailable") from exc
    if code != 0 or len(stdout) < 256:
        return None
    return vpipe.ahash(stdout)


async def _probe_duration(src: Path) -> float:
    """ffprobe 读取时长（秒）。"""
    try:
        _, _, stdout = await ffmpeg.run(
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(src),
            capture_stdout=True,
        )
    except FFmpegError as exc:
        raise VisionError("ffmpeg_unavailable") from exc
    try:
        return float(stdout.decode().strip())
    except ValueError:
        return 0.0


async def _run(*args: str) -> tuple[int, str]:
    """执行 ffmpeg 子进程（共享执行器 + 域异常翻译），返回 (returncode, stderr)。"""
    try:
        return await ffmpeg.run(*args)
    except FFmpegError as exc:
        raise VisionError("ffmpeg_unavailable") from exc


async def _record_failure(
    session: AsyncSession, media_id: int, attempts: int, exc: Exception
) -> None:
    """独立事务记失败（rollback 后执行，不影响本轮其他素材）。"""
    try:
        await session.execute(
            update(KbMedia)
            .where(KbMedia.id == media_id)
            .values(
                process_meta={
                    "visionAttempts": attempts + 1,
                    "visionError": str(exc)[:500],
                }
            )
        )
        await session.commit()
    except Exception:  # noqa: BLE001
        await session.rollback()
        logger.error("kb_vision_failure_record_failed", media_id=media_id)
    logger.warning(
        "kb_vision_media_failed", media_id=media_id, attempts=attempts + 1,
        error=str(exc)[:300],
    )
