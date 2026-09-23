"""费用闸门服务（arch/09 §10.2）：预估与确认入队。

状态机门：``uploaded --estimate--> awaiting_cost --confirm--> queued``，
不经确认不会入队，转写任务只扫 ``queued``。

预估公式：ASR = 时长 × ``unit_prices.asrPerHour``；清洗 token 按口语字符数
折算（≈4 字/秒、≈1.5 字/token）量级估算，仅作分项展示参考。
"""

import math

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.kb import KbMediaKind, KbProcessStatus
from app.core.exceptions import ConflictError, NotFoundError, UnprocessableEntityError
from app.models.kb import KbMedia
from app.repositories.kb import media_repository
from app.schemas.kb import (
    KbCostEstimateItem,
    KbCostEstimateResponse,
)
from app.services.admin.audit_service import record_audit
from app.services.kb.settings_service import get_settings_row
from app.services.kb.source_service import get_source

logger = structlog.get_logger(__name__)

AUDIT_COST_CONFIRM = "kb.cost.confirm"

_SPOKEN_CHARS_PER_SECOND = 4
_CHARS_PER_TOKEN = 1.5


def predict_clean_tokens(seconds: int | float) -> int:
    """清洗 token 预估（≈4 字/秒、≈1.5 字/token，量级参考；用量对照复用）。"""
    return math.ceil(seconds * _SPOKEN_CHARS_PER_SECOND / _CHARS_PER_TOKEN)


async def _load_source_media(
    session: AsyncSession, source_id: int, media_ids: list[int]
) -> list[KbMedia]:
    """读取并校验素材：必须存在、未软删且属于该知识库。"""
    await get_source(session, source_id)
    rows = await media_repository.get_by_ids(session, media_ids)
    found = {row.id for row in rows}
    missing = [mid for mid in media_ids if mid not in found]
    if missing:
        raise NotFoundError(f"素材 {missing[:3]} 不存在或不属于该知识库")
    return rows


async def estimate_cost(
    session: AsyncSession, source_id: int, media_ids: list[int]
) -> KbCostEstimateResponse:
    """分项预估并把 ``uploaded`` 素材推进到 ``awaiting_cost``。

    Raises:
        NotFoundError: 知识库或素材不存在。
        UnprocessableEntityError: ``unit_prices.asrPerHour`` 未配置。
    """
    rows = await _load_source_media(session, source_id, media_ids)
    settings = await get_settings_row(session)
    prices = settings.unit_prices or {}
    asr_per_hour = prices.get("asrPerHour")
    if not asr_per_hour or asr_per_hour <= 0:
        raise UnprocessableEntityError(
            "尚未配置转写单价（kb_settings.unit_prices.asrPerHour），无法预估费用"
        )

    items: list[KbCostEstimateItem] = []
    for row in rows:
        if row.media_kind == KbMediaKind.BOOK:
            # 书的解析/图片费用在批次 C 接入；此处 0 项占位保持分项结构
            items.append(
                KbCostEstimateItem(
                    media_id=row.id,
                    title=row.title,
                    media_kind=row.media_kind,
                    duration_seconds=None,
                    asr_cost=0,
                    clean_tokens=0,
                    estimated_cost=0,
                )
            )
            continue
        seconds = row.duration_seconds or 0
        asr_cost = round(seconds / 3600 * asr_per_hour, 4)
        clean_tokens = predict_clean_tokens(seconds)
        items.append(
            KbCostEstimateItem(
                media_id=row.id,
                title=row.title,
                media_kind=row.media_kind,
                duration_seconds=seconds,
                asr_cost=asr_cost,
                clean_tokens=clean_tokens,
                estimated_cost=asr_cost,
            )
        )
        if row.process_status == KbProcessStatus.UPLOADED:
            row.process_status = KbProcessStatus.AWAITING_COST

    await session.commit()
    total = round(sum(item.estimated_cost for item in items), 4)
    logger.info(
        "kb_cost_estimated",
        source_id=source_id,
        media_count=len(items),
        total=total,
    )
    return KbCostEstimateResponse(currency="CNY", items=items, total=total)


async def confirm_cost(
    session: AsyncSession,
    source_id: int,
    media_ids: list[int],
    *,
    actor_id: int,
    ip: str | None = None,
) -> list[int]:
    """确认费用：``awaiting_cost → queued``（幂等；已入队的跳过）。

    Raises:
        ConflictError: 素材仍是 ``uploaded``——闸门不可跳过。
    """
    rows = await _load_source_media(session, source_id, media_ids)
    queued: list[int] = []
    for row in rows:
        if row.process_status == KbProcessStatus.UPLOADED:
            raise ConflictError(
                f"素材「{row.title}」尚未预估费用，请先执行费用预估（闸门不可跳过）"
            )
        if row.process_status == KbProcessStatus.AWAITING_COST:
            row.process_status = KbProcessStatus.QUEUED
            queued.append(row.id)

    if queued:
        await record_audit(
            session,
            actor_id=actor_id,
            action=AUDIT_COST_CONFIRM,
            detail={"sourceId": source_id, "mediaIds": queued},
            ip=ip,
        )
        await session.commit()
        logger.info(
            "kb_cost_confirmed", source_id=source_id, queued_ids=queued
        )
    return queued
