"""知识点抽取编排（kb-extract 两步编排的第二步）。

对「done 且未抽取」且所属源已发布目录树的素材按滑窗调 LLM 抽取，经
升级门校验与跨窗去重后落库（自动发布或升级人工），失败/空返回独立事务记账。
滑窗规划、校验与去重的纯逻辑在 ``extract_pipeline``；prompt 与模型调用在
``extract_llm``；本轮入口与章节推断在 ``extract_service``。
"""

from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.kb import (
    KB_EXTRACT_MAX_ATTEMPTS,
    KB_EXTRACT_WINDOW_OVERLAP_SEGMENTS,
    KB_EXTRACT_WINDOW_SECONDS,
    KbProcessStatus,
)
from app.core.clock import utc_now
from app.models.kb import KbKnowledgePoint, KbMedia, KbSource
from app.repositories.kb import media_repository, point_repository
from app.services.kb import extract_llm
from app.services.kb import extract_pipeline as xpipe
from app.services.kb.extract_pipeline import WindowSegment
from app.services.kb.settings_service import get_settings_row
from app.services.quota.constants import FEATURE_KB_EXTRACT
from app.services.quota.context import meter_scope

logger = structlog.get_logger(__name__)


async def run_point_extraction(session: AsyncSession, config: Any) -> dict[str, int]:
    from app.agent.runtime.structured import run_structured
    from app.schemas.kb import KbExtractionResult

    stats = {
        "mediasExtracted": 0,
        "pointsCreated": 0,
        "autoPublished": 0,
        "escalated": 0,
        "failedMedias": 0,
        "emptyMedias": 0,
        "awaitingChapterPublish": 0,
    }
    settings = await get_settings_row(session)
    auto_approve = settings.auto_approve_points
    medias = (
        (
            await session.execute(
                select(KbMedia).where(
                    KbMedia.deleted_at.is_(None),
                    KbMedia.process_status == KbProcessStatus.DONE,
                    KbMedia.extracted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    source_rows = (
        await session.execute(
            select(KbSource).where(KbSource.deleted_at.is_(None))
        )
    ).scalars().all()
    sources = {s.id: s for s in source_rows}
    # 失败路径的 rollback 会使 ORM 实例过期——循环前捕获字段，迭代内按 id 重取
    candidates = [(m.id, dict(m.process_meta or {})) for m in medias]
    for media_id, meta in candidates:
        media = await session.get(KbMedia, media_id)
        if media is None:
            continue
        attempts = int(meta.get("extractAttempts") or 0)
        if attempts >= KB_EXTRACT_MAX_ATTEMPTS:
            continue
        source = sources.get(media.source_id)
        published = (source.chapter_tree or {}).get("published") if source else None
        if not published:
            # 生而归章：未发布目录树的源不抽取，等人工门 1 发布后一并处理
            stats["awaitingChapterPublish"] += 1
            continue
        segments = await media_repository.list_segments(session, media_id)
        if not segments:
            continue
        window_segments = [
            WindowSegment(text=seg.text, start_ms=seg.start_ms, end_ms=seg.end_ms)
            for seg in segments
        ]
        windows = xpipe.plan_windows(
            window_segments,
            max_seconds=KB_EXTRACT_WINDOW_SECONDS,
            overlap=KB_EXTRACT_WINDOW_OVERLAP_SEGMENTS,
        )
        try:
            raw_points: list[Any] = []
            for window in windows:
                with meter_scope(
                    None,
                    FEATURE_KB_EXTRACT,
                    detail={"sourceId": media.source_id, "mediaId": media.id},
                ):
                    result = await run_structured(
                        session,
                        result_type=KbExtractionResult,
                        user_prompt=extract_llm.window_prompt(media, window, published),
                        config_id=config.id,
                    )
                raw_points.extend(result.points)
            validated = xpipe.dedup_points(
                xpipe.validate_points(
                    raw_points, window_segments,
                    media_duration_ms=(media.duration_seconds or 0) * 1000,
                    valid_chapters=xpipe.chapter_id_paths(published),
                )
            )
            if not validated:
                # 全窗口 0 点：多为模型空返回，不置 extracted_at，退避重试
                stats["emptyMedias"] += 1
                await _record_empty(session, media_id, meta, attempts)
                continue
            auto_published = await _insert_points(
                session, media, validated, auto_approve=auto_approve
            )
            media.extracted_at = utc_now()
            media.process_meta = {
                **{k: v for k, v in meta.items()
                   if k not in ("extractAttempts", "extractError",
                                "extractSummary", "extractEmptyAt")},
                "extractSummary": {
                    "points": len(validated),
                    "autoPublished": auto_published,
                    "escalated": len(validated) - auto_published,
                },
            }
            stats["mediasExtracted"] += 1
            stats["pointsCreated"] += len(validated)
            stats["autoPublished"] += auto_published
            stats["escalated"] += len(validated) - auto_published
            await session.commit()
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            stats["failedMedias"] += 1
            await _record_failure(session, media_id, meta, attempts, exc)
    return stats


async def _insert_points(
    session: AsyncSession,
    media: KbMedia,
    points: list[xpipe.ValidatedPoint],
    *,
    auto_approve: bool,
) -> int:
    """落库：全绿卡自动发布（置索引脏），带理由卡升级人工；返回自动发布数。

    先 flush 拿 id，再回填 related_ids（同批新点也可互链）。
    """
    rows: list[KbKnowledgePoint] = []
    auto_published = 0
    for point in points:
        publishable = auto_approve and not point.needs_review
        if publishable:
            auto_published += 1
        row = KbKnowledgePoint(
            source_id=media.source_id,
            media_id=media.id,
            point_type=point.point_type,
            title=point.title[:300],
            body=point.body,
            term_definition=point.term_definition,
            applicable_scene=point.applicable_scene,
            excerpt=point.excerpt,
            start_ms=point.start_ms,
            end_ms=point.end_ms,
            related_ids=[],
            chapter_path=list(point.chapter_path),
            status="published" if publishable else "draft",
            needs_review=not publishable,
            review_note=None if publishable else "；".join(point.reasons)[:1000],
            embedding_dirty=publishable,
        )
        session.add(row)
        rows.append(row)
    await session.flush()
    title_to_id = {
        xpipe.normalize_title(title): point_id
        for title, point_id in await point_repository.find_titles(
            session, media.source_id
        )
    }
    for row, point in zip(rows, points, strict=True):
        title_to_id.setdefault(xpipe.normalize_title(row.title), row.id)
        related = xpipe.resolve_related(point.related_titles, title_to_id)
        row.related_ids = [pid for pid in related if pid != row.id]
    return auto_published


async def _record_failure(
    session: AsyncSession, media_id: int, meta: dict[str, Any],
    attempts: int, exc: Exception,
) -> None:
    """独立事务记失败（rollback 后执行，不影响本轮其他素材）。

    meta 由调用方在循环前捕获传入——rollback 会令 ORM 实例过期；
    整体覆写会抹掉 audio_seconds 等其他记账键，必须合并保留。
    """
    try:
        await session.execute(
            update(KbMedia)
            .where(KbMedia.id == media_id)
            .values(
                process_meta={
                    **(meta or {}),
                    "extractAttempts": attempts + 1,
                    "extractError": str(exc)[:500],
                }
            )
        )
        await session.commit()
    except Exception:  # noqa: BLE001
        await session.rollback()
        logger.error("kb_extract_failure_record_failed", media_id=media_id)
    logger.warning(
        "kb_extract_media_failed", media_id=media_id, attempts=attempts + 1,
        error=str(exc)[:300],
    )


async def _record_empty(
    session: AsyncSession, media_id: int, meta: dict[str, Any], attempts: int
) -> None:
    """全窗口 0 点记账：不置 extracted_at，attempts 累计达上限停扫。"""
    try:
        await session.execute(
            update(KbMedia)
            .where(KbMedia.id == media_id)
            .values(
                process_meta={
                    **(meta or {}),
                    "extractAttempts": attempts + 1,
                    "extractEmptyAt": utc_now().isoformat(),
                }
            )
        )
        await session.commit()
    except Exception:  # noqa: BLE001
        await session.rollback()
        logger.error("kb_extract_empty_record_failed", media_id=media_id)
    logger.warning("kb_extract_media_empty", media_id=media_id, attempts=attempts + 1)
