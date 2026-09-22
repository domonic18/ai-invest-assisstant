"""知识库物理清理服务（kb-cleanup internal 任务的执行体）。

清理三类积压（对齐 arch/12 §清理任务设计）：

1. 软删过恢复窗（24h）的 kb_media / kb_source → 删 COS 对象 → 硬删行
   （segment/point/image FK 级联）→ ``pending_cleanup_bytes`` 记账归零；
2. 超龄分片上传会话（process_meta 内 uploadId 超过 7 天）→ abort 释放
   已传分片存储 → 清会话键；
3. deep（每日一次，Redis 门控）：MinIO ``kb/`` 前缀孤儿对象扫描——
   有对象而无对应存活行（含软删未过窗行）即删除。

检索列随行生存（PG 单库无投影层）：软删子行已由软删入口置脏（kb-index
下轮清向量），硬删行向量随 FK 级联消失，purge 无需额外检索面动作。
"""

from datetime import datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.kb import (
    KB_CLEANUP_DEEP_LOCK_KEY,
    KB_CLEANUP_LOCK_KEY,
    KB_SOFT_DELETE_RECOVERY_HOURS,
    KB_UPLOAD_SESSION_MAX_AGE_DAYS,
    KbProcessStatus,
)
from app.core.cache import get_redis
from app.core.clock import utc_now
from app.core.locking import redis_lock
from app.models.kb import KbMedia, KbSource
from app.services.common.minio_service import get_minio_service

logger = structlog.get_logger(__name__)


async def run_cleanup(session: AsyncSession, *, deep: bool = False) -> dict[str, int]:
    """执行一轮清理，返回各分类的清理量（供任务 metadata 记录）。

    Args:
        session: 数据库会话（由调用方创建并关闭）。
        deep: 是否执行孤儿对象扫描（内部有每日一次门控）。
    """
    async with redis_lock(KB_CLEANUP_LOCK_KEY, ttl=600, blocking=False) as ok:
        if not ok:
            logger.info("kb_cleanup_skipped_busy")
            return {"skippedBusy": 1}
        stats = {
            "purgedMedia": 0,
            "purgedSources": 0,
            "purgedBytes": 0,
            "abortedSessions": 0,
            "orphanObjects": 0,
            "orphanBytes": 0,
        }
        minio = get_minio_service()
        cutoff = utc_now() - timedelta(hours=KB_SOFT_DELETE_RECOVERY_HOURS)
        keys_to_remove: list[str] = []

        # 1) 过窗软删素材：硬删行（FK 级联分段/知识点/图片），对象删除后置
        result = await session.execute(
            select(KbMedia).where(
                KbMedia.deleted_at.is_not(None), KbMedia.deleted_at < cutoff
            )
        )
        medias = list(result.scalars())
        if medias:
            keys_to_remove.extend(m.cos_key for m in medias)
            pending_by_source: dict[int, int] = {}
            for m in medias:
                pending_by_source[m.source_id] = (
                    pending_by_source.get(m.source_id, 0) + (m.file_size or 0)
                )
                await session.delete(m)
            for source_id, pending in pending_by_source.items():
                source = await session.get(KbSource, source_id)
                if source is not None:
                    source.pending_cleanup_bytes = max(
                        0, (source.pending_cleanup_bytes or 0) - pending
                    )
            stats["purgedMedia"] = len(medias)
            stats["purgedBytes"] += sum(pending_by_source.values())

        # 2) 过窗软删知识源：连旗下全部素材一起物理清除
        result = await session.execute(
            select(KbSource).where(
                KbSource.deleted_at.is_not(None), KbSource.deleted_at < cutoff
            )
        )
        sources = list(result.scalars())
        for source in sources:
            medias_all = (
                await session.execute(
                    select(KbMedia).where(KbMedia.source_id == source.id)
                )
            ).scalars().all()
            if medias_all:
                keys_to_remove.extend(m.cos_key for m in medias_all)
                stats["purgedBytes"] += sum(m.file_size or 0 for m in medias_all)
                stats["purgedMedia"] += len(medias_all)
                for m in medias_all:
                    await session.delete(m)
            await session.delete(source)
            stats["purgedSources"] += 1

        # 3) 超龄分片会话：abort 释放已传分片，清会话键（行保留待重新上传收养）
        session_cutoff = utc_now() - timedelta(days=KB_UPLOAD_SESSION_MAX_AGE_DAYS)
        result = await session.execute(
            select(KbMedia).where(
                KbMedia.deleted_at.is_(None),
                KbMedia.process_status == KbProcessStatus.UPLOADED,
                KbMedia.file_size == 0,
            )
        )
        for row in result.scalars():
            meta = dict(row.process_meta or {})
            upload_id = meta.get("uploadId")
            if not upload_id:
                continue
            started_at = meta.get("sessionStartedAt")
            try:
                started = (
                    datetime.fromisoformat(started_at) if started_at else None
                )
            except ValueError:
                started = None
            if started is not None and started > session_cutoff:
                continue
            await minio.abort_multipart_upload(row.cos_key, str(upload_id))
            row.process_meta = {
                k: v for k, v in meta.items() if k != "uploadId"
            }
            stats["abortedSessions"] += 1

        await session.commit()

        # 行先落定再删对象：删除失败只产生孤儿，deep 扫描次日自愈；
        # 反过来先删对象则 commit 失败会留下无对象的活行且孤儿扫描永不复删
        if keys_to_remove:
            await minio.remove_files(keys_to_remove)

        # 4) deep 孤儿扫描：有对象而无任何行（含软删未过窗）引用即删
        #    kb/derived/ 前缀是活素材的转写分片缓存（断点续跑依据），非孤儿
        if deep and await _acquire_daily_deep_slot():
            rows = await session.execute(select(KbMedia.cos_key))
            referenced = {key for (key,) in rows}
            objects = await minio.list_object_names("kb/")
            orphans = [
                (name, size)
                for name, size in objects
                if not name.startswith("kb/derived/") and name not in referenced
            ]
            if orphans:
                await minio.remove_files([name for name, _ in orphans])
                stats["orphanObjects"] = len(orphans)
                stats["orphanBytes"] = sum(size for _, size in orphans)

        logger.info("kb_cleanup_done", deep=deep, **stats)
        return stats


async def _acquire_daily_deep_slot() -> bool:
    """每日一次的 deep 扫描门控（SET NX + 24h TTL 标记，非锁）。

    redis_lock 退出即释放，不能做「当日已跑」标记；这里直接 SET NX。
    """
    client = get_redis()
    marked = await client.set(
        f"lock:{KB_CLEANUP_DEEP_LOCK_KEY}", "1", nx=True, ex=86400
    )
    return bool(marked)
