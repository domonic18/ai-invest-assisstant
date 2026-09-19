"""文稿（kb_transcript_segment）编辑服务：读取 + 人工保存 + 脏传播。

文稿是质量的最后防线（arch/12 §4）：编辑器按 seqNo 覆盖分段文本，
仅命中且文本变化的分段置 ``embedding_dirty``（索引任务增量拾取）；
有实际修改时更新 ``kb_media.edited_at``（脏传播源）。
"""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_now
from app.core.exceptions import ConflictError, NotFoundError, UnprocessableEntityError
from app.models.kb import KbMedia
from app.repositories.kb import media_repository
from app.schemas.kb import (
    KbTranscriptResponse,
    KbTranscriptSaveResponse,
    KbTranscriptSegmentView,
    KbTranscriptUpdateRequest,
)
from app.services.admin.audit_service import record_audit
from app.services.kb.media_service import get_media

logger = structlog.get_logger(__name__)

AUDIT_TRANSCRIPT_SAVE = "kb.transcript.save"


async def _load_owned_media(
    session: AsyncSession, source_id: int, media_id: int
) -> KbMedia:
    """读取素材并校验归属（不属于该知识库按 404 处理，不泄露存在性）。"""
    row = await get_media(session, media_id)
    if row.source_id != source_id:
        raise NotFoundError(f"素材 {media_id} 不属于知识库 {source_id}")
    return row


async def get_transcript(
    session: AsyncSession, source_id: int, media_id: int
) -> KbTranscriptResponse:
    """单集文稿读取（按 seqNo 升序；未转写完成为空列表）。"""
    row = await _load_owned_media(session, source_id, media_id)
    segments = await media_repository.list_segments(session, media_id)
    return KbTranscriptResponse(
        media_id=media_id,
        edited_at=row.edited_at,
        segments=[
            KbTranscriptSegmentView(
                seq_no=s.seq_no,
                text=s.text,
                start_ms=s.start_ms,
                end_ms=s.end_ms,
                page_start=s.page_start,
                page_end=s.page_end,
            )
            for s in segments
        ],
    )


async def save_transcript(
    session: AsyncSession,
    source_id: int,
    media_id: int,
    data: KbTranscriptUpdateRequest,
    *,
    actor_id: int,
    ip: str | None = None,
) -> KbTranscriptSaveResponse:
    """文稿批量保存：仅文本变化的分段落库并置脏。

    Raises:
        NotFoundError: 素材不存在 / 不属于该知识库 / 请求含不存在的分段号。
        ConflictError: 素材尚无文稿（未完成转写）。
        UnprocessableEntityError: 请求内分段号重复。
    """
    row = await _load_owned_media(session, source_id, media_id)
    segments = await media_repository.list_segments(session, media_id)
    if not segments:
        raise ConflictError("该素材暂无文稿，无法编辑（转写完成后开放）")

    by_seq = {s.seq_no: s for s in segments}
    requested = [item.seq_no for item in data.segments]
    if len(requested) != len(set(requested)):
        raise UnprocessableEntityError("请求内存在重复的分段号")
    missing = sorted(set(requested) - set(by_seq))
    if missing:
        raise NotFoundError(f"分段 {missing[0]} 不存在")

    updated = 0
    for item in data.segments:
        seg = by_seq[item.seq_no]
        if seg.text == item.text:
            continue
        seg.text = item.text
        seg.embedding_dirty = True
        updated += 1

    edited_at = None
    if updated:
        row.edited_at = utc_now()
        edited_at = row.edited_at
    await record_audit(
        session,
        actor_id=actor_id,
        action=AUDIT_TRANSCRIPT_SAVE,
        detail={"mediaId": media_id, "updated": updated},
        ip=ip,
    )
    await session.commit()
    logger.info("kb_transcript_saved", media_id=media_id, updated=updated)
    return KbTranscriptSaveResponse(
        media_id=media_id, edited_at=edited_at, updated_count=updated
    )
