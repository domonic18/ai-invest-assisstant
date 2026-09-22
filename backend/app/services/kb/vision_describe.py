"""课程视频关键帧：VLM 描述阶段（按张计费）。

扫 ``describe_status='pending'`` 帧行 → ``run_structured(ImageUnderstanding,
images=[帧])``（vision 槽位 + kb_vision 台账），prompt 附前后句文稿 →
三文本回填置脏 → 失败退避 ``describe_attempts``（≥3 终态 failed）。
单帧描述失败退避重试，不影响其他帧。
"""

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.kb import (
    KB_VISION_DESCRIBE_BATCH_SIZE,
    KB_VISION_MAX_DESCRIBE_ATTEMPTS,
    KbDescribeStatus,
)
from app.models.kb import KbImageAsset, KbMedia
from app.repositories.kb import media_repository
from app.services.common.minio_service import get_minio_service
from app.services.kb.vision_common import _fmt_ms
from app.services.quota.constants import FEATURE_KB_VISION
from app.services.quota.context import meter_scope

logger = structlog.get_logger(__name__)


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
                    KbImageAsset.describe_status == KbDescribeStatus.PENDING,
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
    media_info = {
        media.id: (media.title, media.episode_no, media.source_id) for _, media in rows
    }
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
            if row is None or row.describe_status != KbDescribeStatus.PENDING:
                continue
            image_bytes = await minio.download_file(row.cos_key)
            title, episode_no, source_id = media_info[media_id]
            prompt = _describe_prompt(title, episode_no, segments, start_ms)
            with meter_scope(
                None,
                FEATURE_KB_VISION,
                detail={"sourceId": source_id, "mediaId": media_id},
            ):
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
        row.describe_status = KbDescribeStatus.DONE
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
            row.describe_status = KbDescribeStatus.FAILED
        await session.commit()
    except Exception:  # noqa: BLE001
        await session.rollback()
        logger.error("kb_vision_describe_failure_record_failed", image_id=row_id)
    logger.warning(
        "kb_vision_describe_failed", image_id=row_id, error=str(exc)[:300],
    )
