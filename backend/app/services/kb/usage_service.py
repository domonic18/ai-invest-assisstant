"""建库用量聚合（批次 G1，arch/12 §10.2）。

台账侧：``user_token_usage`` 按 ``kb_*`` feature × 模型汇出 token 明细
（source 过滤走 ``detail.sourceId`` 上下文，Python 侧归集——行量千级，
不值得 JSONB SQL 过滤牺牲 sqlite 可测性）。
ASR 侧：``kb_media.process_meta.audio_seconds`` × ``unit_prices.asrPerHour``
（ASR 按时长计费不走 token 台账）。
预估 vs 实际对照：ASR 时长对照 ``duration_seconds`` 登记口径；清洗 token
对照 cost_service 的字符折算公式。素材按上传时间（``created_at``）归集，
软删行保留——已发生的花费不因删库消失。
"""

from datetime import date, datetime, time, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import CN_TZ
from app.models.account_quota import UserTokenUsage
from app.models.kb import KbMedia
from app.schemas.kb import KbUsageAsr, KbUsageResponse, KbUsageTokenItem
from app.services.kb.cost_service import predict_clean_tokens
from app.services.kb.settings_service import get_settings_row
from app.services.quota.constants import (
    FEATURE_KB_CLEAN,
    FEATURE_KB_EMBED,
    FEATURE_KB_EXTRACT,
    FEATURE_KB_OPTIMIZE,
    FEATURE_KB_VISION,
)

logger = structlog.get_logger(__name__)

KB_USAGE_FEATURES: tuple[str, ...] = (
    FEATURE_KB_CLEAN,
    FEATURE_KB_EXTRACT,
    FEATURE_KB_VISION,
    FEATURE_KB_EMBED,
    FEATURE_KB_OPTIMIZE,
)


def _range_bounds(
    date_from: date | None, date_to: date | None
) -> tuple[datetime | None, datetime | None]:
    """日期区间 → aware 时间戳边界（北京日历日起点 / 终点次日零点开区间）。"""
    start = (
        datetime.combine(date_from, time.min, tzinfo=CN_TZ) if date_from else None
    )
    end = (
        datetime.combine(date_to, time.min, tzinfo=CN_TZ) + timedelta(days=1)
        if date_to
        else None
    )
    return start, end


async def get_usage(
    session: AsyncSession,
    *,
    source_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> KbUsageResponse:
    """聚合建库用量（token 分项 + ASR 时长 × 单价 + 预估对照）。"""
    start, end = _range_bounds(date_from, date_to)

    ledger_stmt = select(
        UserTokenUsage.feature,
        UserTokenUsage.model_name,
        UserTokenUsage.prompt_tokens,
        UserTokenUsage.completion_tokens,
        UserTokenUsage.total_tokens,
        UserTokenUsage.detail,
    ).where(UserTokenUsage.feature.in_(KB_USAGE_FEATURES))
    if start is not None:
        ledger_stmt = ledger_stmt.where(UserTokenUsage.created_at >= start)
    if end is not None:
        ledger_stmt = ledger_stmt.where(UserTokenUsage.created_at < end)
    ledger_rows = (await session.execute(ledger_stmt)).all()

    media_stmt = select(KbMedia.duration_seconds, KbMedia.process_meta).where(
        KbMedia.media_kind != "book"
    )
    if source_id is not None:
        media_stmt = media_stmt.where(KbMedia.source_id == source_id)
    if start is not None:
        media_stmt = media_stmt.where(KbMedia.created_at >= start)
    if end is not None:
        media_stmt = media_stmt.where(KbMedia.created_at < end)
    media_rows = (await session.execute(media_stmt)).all()

    grouped: dict[tuple[str, str], list[int]] = {}
    clean_tokens_actual = 0
    for feature, model_name, pt, ct, tt, detail in ledger_rows:
        if source_id is not None and (detail or {}).get("sourceId") != source_id:
            continue
        agg = grouped.setdefault((feature, model_name), [0, 0, 0, 0])
        agg[0] += 1
        agg[1] += pt
        agg[2] += ct
        agg[3] += tt
        if feature == FEATURE_KB_CLEAN:
            clean_tokens_actual += tt

    settings = await get_settings_row(session)
    prices = settings.unit_prices or {}
    asr_per_hour = prices.get("asrPerHour")
    vlm_per_image = prices.get("vlmPerImage")

    audio_seconds = 0.0
    estimated_seconds = 0
    clean_tokens_predicted = 0
    media_count = 0
    for duration_seconds, process_meta in media_rows:
        actual = (process_meta or {}).get("audio_seconds")
        if not actual:
            continue
        media_count += 1
        audio_seconds += float(actual)
        estimated_seconds += duration_seconds or 0
        clean_tokens_predicted += predict_clean_tokens(duration_seconds or 0)

    asr_cost = (
        round(audio_seconds / 3600 * asr_per_hour, 4)
        if asr_per_hour and audio_seconds > 0
        else None
    )
    feature_order = {name: i for i, name in enumerate(KB_USAGE_FEATURES)}
    token_items: list[KbUsageTokenItem] = []
    total_cost = asr_cost or 0.0
    for (feature, model_name), (calls, pt, ct, tt) in sorted(
        grouped.items(), key=lambda kv: (feature_order.get(kv[0][0], 99), kv[0][1])
    ):
        estimated_cost = None
        if feature == FEATURE_KB_VISION and vlm_per_image:
            estimated_cost = round(calls * vlm_per_image, 4)
            total_cost += estimated_cost
        token_items.append(
            KbUsageTokenItem(
                feature=feature,
                model_name=model_name,
                calls=calls,
                prompt_tokens=pt,
                completion_tokens=ct,
                total_tokens=tt,
                estimated_cost=estimated_cost,
            )
        )

    logger.info(
        "kb_usage_aggregated",
        source_id=source_id,
        token_items=len(token_items),
        media_count=media_count,
        total_cost=total_cost,
    )
    return KbUsageResponse(
        source_id=source_id,
        date_from=date_from,
        date_to=date_to,
        token_items=token_items,
        asr=KbUsageAsr(
            media_count=media_count,
            audio_seconds=round(audio_seconds, 1),
            estimated_seconds=estimated_seconds,
            cost_per_hour=asr_per_hour,
            cost=asr_cost,
        ),
        clean_tokens_predicted=clean_tokens_predicted,
        clean_tokens_actual=clean_tokens_actual,
        total_cost=round(total_cost, 4),
    )
