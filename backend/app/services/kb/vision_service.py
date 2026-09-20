"""课程视频关键帧服务（kb-vision internal 任务的执行体，arch/12 §4.1）。

两段式成本分层：

1. 选帧阶段（零 LLM）：扫 ``done 且 vision_at 为空`` 的 video 素材 →
   下载源文件 → 三路信号选帧（vision_pipeline 纯函数）→ ffmpeg 抽帧 +
   aHash 近重复过滤 → 原图/缩略图传 COS derived 前缀 → ``kb_image_asset``
   行（pending）→ ``vision_at`` 记账（幂等键，重跑不重抽）；
2. 描述阶段（按张计费）：扫 ``describe_status='pending'`` 帧行 →
   ``run_structured(ImageUnderstanding, images=[帧])``（vision 槽位 +
   kb_vision 台账），prompt 附前后句文稿 → 三文本回填置脏 → 失败退避
   ``describe_attempts``（≥3 终态 failed）。

失败语义：单集选帧失败回滚后独立写 ``process_meta.visionAttempts/
visionError``，累计不再扫；单帧描述失败退避重试，不影响其他帧。
"""

import asyncio
import tempfile
from datetime import timedelta
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.kb import (
    KB_VISION_DESCRIBE_BATCH_SIZE,
    KB_VISION_FIXED_INTERVAL_SECONDS,
    KB_VISION_LOCK_KEY,
    KB_VISION_MAX_DESCRIBE_ATTEMPTS,
    KB_VISION_MAX_FRAMES_PER_MEDIA,
    KB_VISION_MAX_MEDIA_ATTEMPTS,
    KB_VISION_MERGE_WINDOW_SECONDS,
    KB_VISION_PHASH_HAMMING_THRESHOLD,
    KB_VISION_SCENE_THRESHOLD,
    KB_VISION_SEEK_TOLERANCE_SECONDS,
)
from app.core.clock import utc_now
from app.core.exceptions import ConflictError, NotFoundError, UnprocessableEntityError
from app.core.locking import redis_lock
from app.models.kb import KbImageAsset, KbMedia
from app.repositories.kb import media_repository
from app.schemas.kb import KbImageAssetResponse, KbImageListResponse
from app.services.admin.audit_service import record_audit
from app.services.common.minio_service import get_minio_service
from app.services.kb import vision_pipeline as vpipe
from app.services.kb.settings_service import resolve_role_model
from app.services.kb.source_service import get_source
from app.services.quota.constants import FEATURE_KB_VISION
from app.services.quota.context import meter_scope

logger = structlog.get_logger(__name__)

_FRAME_KEY_TEMPLATE = "kb/derived/{media_id}/frames/{start_ms:012d}{suffix}.jpg"

AUDIT_IMAGE_REDESCRIBE = "kb.image.redescribe"
AUDIT_IMAGE_EXCLUDE = "kb.image.exclude"


class VisionError(RuntimeError):
    """视觉管线本机环节失败（ffmpeg 缺失/失败、素材不可读）。"""


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


# ---------------------------------------------------------------------------
# 阶段一：选帧（零 LLM）
# ---------------------------------------------------------------------------


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
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-ss", f"{seek:.3f}", "-i", str(src),
            "-frames:v", "1", "-vf", "scale=16:16",
            "-f", "rawvideo", "-pix_fmt", "gray", "-",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
    except FileNotFoundError as exc:
        raise VisionError("ffmpeg_unavailable") from exc
    if proc.returncode != 0 or len(stdout) < 256:
        return None
    return vpipe.ahash(stdout)


async def _probe_duration(src: Path) -> float:
    """ffprobe 读取时长（秒）。"""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(src),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
    except FileNotFoundError as exc:
        raise VisionError("ffmpeg_unavailable") from exc
    try:
        return float(stdout.decode().strip())
    except ValueError:
        return 0.0


async def _run(*args: str) -> tuple[int, str]:
    """执行 ffmpeg 子进程，返回 (returncode, stderr)。"""
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
    except FileNotFoundError as exc:
        raise VisionError("ffmpeg_unavailable") from exc
    return proc.returncode or 0, stderr.decode(errors="replace")


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


# ---------------------------------------------------------------------------
# 阶段二：VLM 描述（按张计费）
# ---------------------------------------------------------------------------


async def _describe_frames(session: AsyncSession, config: Any) -> dict[str, int]:
    from app.agent.runtime.structured import run_structured
    from app.schemas.kb import ImageUnderstanding

    stats = {"framesDescribed": 0, "describeFailed": 0}
    rows = (
        (
            await session.execute(
                select(KbImageAsset, KbMedia)
                .join(KbMedia, KbImageAsset.media_id == KbMedia.id)
                .where(
                    KbImageAsset.describe_status == "pending",
                    KbImageAsset.describe_attempts < KB_VISION_MAX_DESCRIBE_ATTEMPTS,
                    KbMedia.deleted_at.is_(None),
                    KbMedia.media_kind == "video",
                )
                .order_by(KbImageAsset.media_id, KbImageAsset.start_ms)
                .limit(KB_VISION_DESCRIBE_BATCH_SIZE)
            )
        )
        .all()
    )
    # 失败路径的 rollback 会使 ORM 实例过期——预先物化为纯数据，迭代内按 id 重取
    plan = [(row.id, media.id, row.start_ms or 0) for row, media in rows]
    media_info = {media.id: (media.title, media.episode_no) for _, media in rows}
    minio = get_minio_service()
    current_media_id: int | None = None
    segments: list[tuple[int | None, int | None, str]] = []
    for row_id, media_id, start_ms in plan:
        if media_id != current_media_id:
            current_media_id = media_id
            raw = await media_repository.list_segments(session, media_id)
            segments = [(s.start_ms, s.end_ms, s.text) for s in raw]
        try:
            row = await session.get(KbImageAsset, row_id)
            if row is None or row.describe_status != "pending":
                continue
            image_bytes = await minio.download_file(row.cos_key)
            title, episode_no = media_info[media_id]
            prompt = _describe_prompt(title, episode_no, segments, start_ms)
            with meter_scope(None, FEATURE_KB_VISION):
                result = await run_structured(
                    session,
                    result_type=ImageUnderstanding,
                    user_prompt=prompt,
                    images=[(image_bytes, "image/jpeg")],
                    config_id=config.id,
                )
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            stats["describeFailed"] += 1
            await _record_describe_failure(session, row_id, exc)
            continue
        row.text_in_image = result.text_in_image
        row.caption = result.caption
        row.vision_description = result.description
        row.describe_status = "done"
        row.embedding_dirty = True
        stats["framesDescribed"] += 1
        await session.commit()
    return stats


def _describe_prompt(
    title: str, episode_no: int | None,
    segments: list[tuple[int | None, int | None, str]], start_ms: int,
) -> str:
    """描述 prompt：附该时间码前后句文稿作上下文（书图前后页文本同款技巧）。"""
    context = _surrounding_text(segments, start_ms)
    episode = f"第 {episode_no} 集" if episode_no else ""
    return (
        f"这是金融课程「{title}」{episode} 视频在第 "
        f"{_fmt_ms(start_ms)} 处的关键帧。请结合文稿上下文描述该画面：\n"
        "- text_in_image：画面中出现的全部文字（无则输出空串）\n"
        "- caption：一句话图注（画面主体，保留课程术语）\n"
        "- description：画面内容描述（K 线形态/指标/走势方向等，供检索）\n\n"
        f"文稿上下文：\n{context}"
    )


def _surrounding_text(
    segments: list[tuple[int | None, int | None, str]], start_ms: int
) -> str:
    """取覆盖该时间码的分句及前后各一句。"""
    index = next(
        (
            i
            for i, (start, end, _) in enumerate(segments)
            if (start or 0) <= start_ms <= (end or 0)
        ),
        None,
    )
    if index is None:
        index = next(
            (i for i, (start, _, _) in enumerate(segments) if (start or 0) > start_ms),
            len(segments),
        )
    near = segments[max(0, index - 1): index + 2]
    if not near:
        return "（无文稿）"
    return "\n".join(
        f"[{_fmt_ms(start)}] {text}" for start, _, text in near
    )


async def _record_describe_failure(
    session: AsyncSession, row_id: int, exc: Exception
) -> None:
    """独立事务退避：attempts+1，达上限置终态 failed。"""
    try:
        row = await session.get(KbImageAsset, row_id)
        if row is None:
            return
        row.describe_attempts += 1
        if row.describe_attempts >= KB_VISION_MAX_DESCRIBE_ATTEMPTS:
            row.describe_status = "failed"
        await session.commit()
    except Exception:  # noqa: BLE001
        await session.rollback()
        logger.error("kb_vision_describe_failure_record_failed", image_id=row_id)
    logger.warning(
        "kb_vision_describe_failed", image_id=row_id, error=str(exc)[:300],
    )


def _fmt_ms(ms: int | None) -> str:
    if ms is None:
        return "?"
    total_seconds = ms // 1000
    return f"{total_seconds // 60:02d}:{total_seconds % 60:02d}"


# ---------------------------------------------------------------------------
# 管理端图片资产列表（批次 E 检索消费前的可见性入口）
# ---------------------------------------------------------------------------

_THUMB_URL_TTL = timedelta(hours=1)


async def list_images(
    session: AsyncSession,
    source_id: int,
    *,
    media_id: int | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> KbImageListResponse:
    """图片资产分页列表（书嵌图 + 课程关键帧，缩略图短时效签名）。"""
    await get_source(session, source_id)
    conditions = [KbImageAsset.source_id == source_id]
    if media_id is not None:
        conditions.append(KbImageAsset.media_id == media_id)
    if status is not None:
        conditions.append(KbImageAsset.describe_status == status)
    total = (
        await session.execute(
            select(func.count()).select_from(KbImageAsset).where(*conditions)
        )
    ).scalar_one()
    rows = (
        (
            await session.execute(
                select(KbImageAsset)
                .where(*conditions)
                .order_by(KbImageAsset.media_id, KbImageAsset.start_ms, KbImageAsset.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    minio = get_minio_service()
    items = [
        await _image_response(minio, row)
        for row in rows
    ]
    return KbImageListResponse(items=items, total=total)


async def _image_response(
    minio: Any, row: KbImageAsset
) -> KbImageAssetResponse:
    return KbImageAssetResponse(
        id=row.id,
        source_id=row.source_id,
        media_id=row.media_id,
        page_no=row.page_no,
        start_ms=row.start_ms,
        end_ms=row.end_ms,
        thumb_url=await minio.get_presigned_url(
            row.thumb_cos_key or row.cos_key, expires=_THUMB_URL_TTL
        ),
        describe_status=row.describe_status,
        describe_attempts=row.describe_attempts,
        text_in_image=row.text_in_image,
        caption=row.caption,
        vision_description=row.vision_description,
        index_excluded=row.index_excluded,
        created_at=row.created_at,
    )


async def redescribe_image(
    session: AsyncSession,
    image_id: int,
    *,
    actor_id: int,
    ip: str | None = None,
) -> KbImageAssetResponse:
    """重新描述：置回 pending 重跑（清旧文本，下一轮 kb-vision 拾起）。"""
    row = await session.get(KbImageAsset, image_id)
    if row is None:
        raise NotFoundError("图片资产不存在")
    media = await session.get(KbMedia, row.media_id)
    if media is None or media.deleted_at is not None:
        raise ConflictError("所属素材已删除，无法重新描述")
    if media.media_kind != "video":
        raise ConflictError("仅课程视频关键帧支持重新描述")
    row.describe_status = "pending"
    row.describe_attempts = 0
    row.text_in_image = None
    row.caption = None
    row.vision_description = None
    row.embedding_dirty = True
    await record_audit(
        session,
        actor_id=actor_id,
        action=AUDIT_IMAGE_REDESCRIBE,
        detail={"imageId": image_id, "mediaId": row.media_id},
        ip=ip,
    )
    await session.commit()
    return await _image_response(get_minio_service(), row)


async def set_image_excluded(
    session: AsyncSession,
    image_id: int,
    excluded: bool,
    *,
    actor_id: int,
    ip: str | None = None,
) -> KbImageAssetResponse:
    """索引排除开关：排除置脏（批次 E 检索索引构建时过滤并清理）。"""
    row = await session.get(KbImageAsset, image_id)
    if row is None:
        raise NotFoundError("图片资产不存在")
    if row.index_excluded != excluded:
        row.index_excluded = excluded
        row.embedding_dirty = True
        await record_audit(
            session,
            actor_id=actor_id,
            action=AUDIT_IMAGE_EXCLUDE,
            detail={"imageId": image_id, "excluded": excluded},
            ip=ip,
        )
        await session.commit()
    return await _image_response(get_minio_service(), row)
