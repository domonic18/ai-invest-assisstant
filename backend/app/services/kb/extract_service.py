"""知识点抽取服务（kb-extract internal 任务的执行体，arch/12 §6）。

两步编排：

1. 章节推断：``draft`` 为空且启用的知识源 → 逐集大纲（EpisodeOutline）→
   跨集合并单次调用（ChapterTreeDraft）→ 服务层按位置赋 id 写
   ``chapter_tree.draft``（发布由管理端审核后覆写 published）；
2. 知识点抽取：``done 且未抽取``的素材按滑窗（≤600s，1 段重叠）调
   结构化抽取（KbExtractionResult）→ 三层防线（时间码 clamp、excerpt
   归一化命中、related_titles 回链剔除）→ 跨窗去重 → 草稿落库 →
   ``extracted_at`` 记账。

失败语义：单素材失败回滚后独立写 ``process_meta.extractAttempts/
extractError``，累计 KB_EXTRACT_MAX_ATTEMPTS 不再扫（防毒素材烧 token）；
章节推断失败仅记日志下轮重试。
"""

import json
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.kb import (
    KB_EXTRACT_LOCK_KEY,
    KB_EXTRACT_MAX_ATTEMPTS,
    KB_EXTRACT_WINDOW_OVERLAP_SEGMENTS,
    KB_EXTRACT_WINDOW_SECONDS,
)
from app.core.clock import utc_now
from app.core.exceptions import UnprocessableEntityError
from app.core.locking import redis_lock
from app.models.kb import KbKnowledgePoint, KbMedia, KbSource
from app.repositories.kb import media_repository, point_repository
from app.services.kb import extract_pipeline as xpipe
from app.services.kb.extract_pipeline import WindowSegment
from app.services.kb.settings_service import resolve_role_model
from app.services.quota.constants import FEATURE_KB_EXTRACT
from app.services.quota.context import meter_scope

logger = structlog.get_logger(__name__)


async def run_extraction(session: AsyncSession) -> dict[str, int]:
    """执行一轮抽取，返回分类统计（spider 据此判 SKIPPED）。"""
    async with redis_lock(KB_EXTRACT_LOCK_KEY, ttl=3600, blocking=False) as ok:
        if not ok:
            logger.info("kb_extract_skipped_busy")
            return {"skippedBusy": 1}
        try:
            config = await resolve_role_model(session, "extract")
        except UnprocessableEntityError:
            logger.info("kb_extract_no_model_configured")
            return {"noModelConfigured": 1}
        stats = {
            "chaptersInferred": 0,
            "mediasExtracted": 0,
            "pointsCreated": 0,
            "failedMedias": 0,
        }
        stats.update(await _infer_chapters(session, config))
        stats.update(await _extract_points(session, config))
        logger.info("kb_extract_done", **stats)
        return stats


# ---------------------------------------------------------------------------
# 章节推断
# ---------------------------------------------------------------------------


async def _infer_chapters(session: AsyncSession, config: Any) -> dict[str, int]:
    from app.agent.runtime.structured import run_structured
    from app.schemas.kb import ChapterTreeDraft, EpisodeOutline

    stats = {"chaptersInferred": 0}
    sources = (
        (
            await session.execute(
                select(KbSource).where(
                    KbSource.deleted_at.is_(None), KbSource.enabled.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )
    for source in sources:
        tree = dict(source.chapter_tree or {})
        if tree.get("draft") is not None:
            continue
        medias = [
            m
            for m in await media_repository.list_by_source(session, source.id)
            if m.process_status == "done"
        ]
        outlines: list[EpisodeOutline] = []
        for media in medias:
            segments = await media_repository.list_segments(session, media.id)
            if not segments:
                continue
            try:
                outlines.append(
                    await _outline_for_media(session, config, media, segments)
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "kb_extract_outline_failed",
                    source_id=source.id,
                    media_id=media.id,
                    error=str(exc)[:300],
                )
        if not outlines:
            continue
        outline_payload = [
            {
                "episode_no": o.episode_no,
                "points": [{"title": p.title, "summary": p.summary} for p in o.points],
            }
            for o in outlines
        ]
        prompt = (
            "你是全书目录主编。以下是同一课程各集大纲（JSON 数组），请合并为"
            "全书目录树：顶层 3~10 个章节，每章 children 为该章下的小节列表"
            "（可为空数组）。章节/小节标题从大纲条目归纳提升，不要照抄全部条目，"
            "也不要编造大纲之外的内容。\n\n"
            f"{json.dumps(outline_payload, ensure_ascii=False, indent=1)}"
        )
        try:
            with meter_scope(None, FEATURE_KB_EXTRACT):
                merged = await run_structured(
                    session, result_type=ChapterTreeDraft, user_prompt=prompt,
                    config_id=config.id,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "kb_extract_chapter_merge_failed",
                source_id=source.id,
                error=str(exc)[:300],
            )
            continue
        tree["draft"] = xpipe.assign_chapter_ids(merged)
        source.chapter_tree = tree
        stats["chaptersInferred"] += 1
        await session.commit()
    return stats


async def _outline_for_media(
    session: AsyncSession,
    config: Any,
    media: KbMedia,
    segments: list[Any],
) -> Any:
    """单集大纲：全文阅读后输出条目列表（episode_no 由 prompt 固定）。"""
    from app.agent.runtime.structured import run_structured
    from app.schemas.kb import EpisodeOutline

    episode_no = media.episode_no or 0
    numbered = "\n".join(f"{i}. {seg.text}" for i, seg in enumerate(segments, start=1))
    prompt = (
        f"你是课程目录编辑。阅读第 {episode_no} 集「{media.title}」的逐句文稿，"
        "提炼本集知识大纲：3~8 个条目、按讲解顺序，每条含 title（小节标题）与"
        " summary（一句话概括）。episode_no 固定输出 "
        f"{episode_no}。只依据文稿内容，不要编造。\n\n文稿：\n{numbered}"
    )
    with meter_scope(None, FEATURE_KB_EXTRACT):
        return await run_structured(
            session, result_type=EpisodeOutline, user_prompt=prompt,
            config_id=config.id,
        )


# ---------------------------------------------------------------------------
# 知识点抽取
# ---------------------------------------------------------------------------


async def _extract_points(session: AsyncSession, config: Any) -> dict[str, int]:
    from app.agent.runtime.structured import run_structured
    from app.schemas.kb import KbExtractionResult

    stats = {"mediasExtracted": 0, "pointsCreated": 0, "failedMedias": 0}
    medias = (
        (
            await session.execute(
                select(KbMedia).where(
                    KbMedia.deleted_at.is_(None),
                    KbMedia.process_status == "done",
                    KbMedia.extracted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    for media in medias:
        media_id = media.id
        meta = dict(media.process_meta or {})
        attempts = int(meta.get("extractAttempts") or 0)
        if attempts >= KB_EXTRACT_MAX_ATTEMPTS:
            continue
        segments = await media_repository.list_segments(session, media.id)
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
                with meter_scope(None, FEATURE_KB_EXTRACT):
                    result = await run_structured(
                        session,
                        result_type=KbExtractionResult,
                        user_prompt=_window_prompt(media, window),
                        config_id=config.id,
                    )
                raw_points.extend(result.points)
            validated = xpipe.dedup_points(
                xpipe.validate_points(
                    raw_points, window_segments,
                    media_duration_ms=(media.duration_seconds or 0) * 1000,
                )
            )
            await _insert_points(session, media, validated)
            media.extracted_at = utc_now()
            media.process_meta = {
                k: v
                for k, v in meta.items()
                if k not in ("extractAttempts", "extractError")
            }
            stats["mediasExtracted"] += 1
            stats["pointsCreated"] += len(validated)
            await session.commit()
        except Exception as exc:  # noqa: BLE001
            # rollback 已使 media 实例过期，媒体 id 须在循环头预捕获
            await session.rollback()
            stats["failedMedias"] += 1
            await _record_failure(session, media_id, attempts, exc)
    return stats


async def _insert_points(
    session: AsyncSession, media: KbMedia, points: list[xpipe.ValidatedPoint],
) -> None:
    """草稿落库：先 flush 拿 id，再回填 related_ids（同批新点也可互链）。"""
    rows: list[KbKnowledgePoint] = []
    for point in points:
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
            chapter_path=[],
            status="draft",
            needs_review=point.needs_review,
            embedding_dirty=False,
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


def _window_prompt(media: KbMedia, window: list[WindowSegment]) -> str:
    lines = []
    for seg in window:
        timecode = _fmt_ms(seg.start_ms) if seg.start_ms is not None else "P?"
        lines.append(f"[{timecode}] {seg.text}")
    return (
        "你是金融课程知识整理员。从下面的文稿片段中抽取可独立成立的知识点卡片。\n"
        "要求：\n"
        "- point_type 取 concept/theorem/method/discipline/case 之一\n"
        "- excerpt 必须原样摘抄文稿中连续的一句或几句原文\n"
        "- start_ms/end_ms 为该知识点讲解起止毫秒时间码，按各行行首 [mm:ss] "
        "估算；无法判断输出 null\n"
        "- related_titles 填与之相关的其他知识点标题，可为空列表\n"
        "- term_definition/applicable_scene 无内容输出空串\n"
        "- 不编造文稿中没有的内容；本窗口没有新知识点时输出空 points\n\n"
        f"课程「{media.title}」文稿（行首为该句起始时间）：\n" + "\n".join(lines)
    )


def _fmt_ms(ms: int | None) -> str:
    if ms is None:
        return "?"
    total_seconds = ms // 1000
    return f"{total_seconds // 60:02d}:{total_seconds % 60:02d}"


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
