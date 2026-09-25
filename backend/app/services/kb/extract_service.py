"""知识点抽取服务（kb-extract internal 任务的执行体，arch/09 §6）。

两步编排：

1. 章节推断：启用的知识源中存在未入树素材（``process_meta.outlineAt``
   缺失的 done 素材）→ 逐集大纲（EpisodeOutline）→ 与已有 draft 合并
   （首次为全量合并，ChapterTreeDraft）→ 服务层按位置赋 id 写
   ``chapter_tree.draft``，并对本次并入素材记 ``outlineAt``（发布由
   管理端审核后覆写 published；新素材到达即增量重推断）；
2. 知识点抽取：``done 且未抽取``且所属源已发布目录树的素材按滑窗
   （≤600s，1 段重叠）调结构化抽取（KbExtractionResult，prompt 携带
   published 目录树，知识点生而带 chapter_path 与 confidence）→
   升级门校验（时间码 clamp、摘录锚定替换、章节链修剪、置信度、case 卡）
   → 跨窗去重 → 自动发布或升级人工 → ``extracted_at`` 记账；
   全窗口 0 点不记账，按 ``extractAttempts`` 重试（防模型空返回永久
   漏采，达 KB_EXTRACT_MAX_ATTEMPTS 停扫）。

审核语义（HITL）：``kb_settings.auto_approve_points`` 开启时，无任何升级
理由的卡直接 ``published`` 并置索引脏；有理由的卡落 ``draft`` 且
``review_note`` 写明理由清单，由人工在工作台定夺。

失败语义：单素材失败回滚后独立写 ``process_meta.extractAttempts/
extractError``，累计 KB_EXTRACT_MAX_ATTEMPTS 不再扫（防毒素材烧 token）；
章节推断失败仅记日志下轮重试。

模块分层：本模块持有并发锁与章节推断编排；知识点抽取编排与失败记账在
``extract_points``；prompt 构造与 ``run_structured`` 调用封装在 ``extract_llm``；
滑窗/校验/去重纯逻辑在 ``extract_pipeline``。
"""

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.kb import KB_EXTRACT_LOCK_KEY, KbProcessStatus
from app.core.clock import utc_now
from app.core.exceptions import UnprocessableEntityError
from app.core.locking import redis_lock
from app.models.kb import KbMedia, KbSource
from app.repositories.kb import media_repository
from app.services.kb import extract_llm
from app.services.kb import extract_pipeline as xpipe
from app.services.kb.extract_points import run_point_extraction
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
        stats.update(await run_point_extraction(session, config))
        logger.info("kb_extract_done", **stats)
        return stats


async def _infer_chapters(session: AsyncSession, config: Any) -> dict[str, int]:
    from app.agent.runtime.structured import run_structured
    from app.schemas.kb import ChapterTreeDraft

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
        medias = [
            m
            for m in await media_repository.list_by_source(session, source.id)
            if m.process_status == KbProcessStatus.DONE
        ]
        # 增量入树：只对未记 outlineAt 的 done 素材出大纲（首次即全量）
        pending = [m for m in medias if not (m.process_meta or {}).get("outlineAt")]
        if not pending:
            continue
        base = tree.get("draft")
        outlines: list[Any] = []
        outlined: list[KbMedia] = []
        for media in pending:
            segments = await media_repository.list_segments(session, media.id)
            if not segments:
                continue
            try:
                outlines.append(
                    await extract_llm.outline_for_media(session, config, media, segments)
                )
                outlined.append(media)
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
        try:
            with meter_scope(None, FEATURE_KB_EXTRACT, detail={"sourceId": source.id}):
                merged = await run_structured(
                    session, result_type=ChapterTreeDraft,
                    user_prompt=extract_llm.chapter_merge_prompt(base, outline_payload),
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
        # 入树标记与树写同事务：合并失败回滚则不记标，下轮重推
        for media in outlined:
            media.process_meta = {
                **(media.process_meta or {}),
                "outlineAt": utc_now().isoformat(),
            }
        await session.commit()
    return stats
