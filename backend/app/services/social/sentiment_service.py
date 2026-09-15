"""情绪判断服务：批量调 LLM 判待判内容，判后立即清稿（合规边界）。

单轮 ≤ SOCIAL_JUDGE_BATCH_SIZE 条，redis 锁防并发重入；LLM 失败抛
``SocialJudgmentNotReadyError`` 由 celery 按 10 分钟退避重试。幻觉防御
双保险：LLM 编造的 post_id 直接忽略（条目保持待判），编造/不在基本表的
个股标的剔除。
"""

import json
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.social import (
    SOCIAL_JUDGE_BATCH_SIZE,
    SOCIAL_SENTIMENT_LOCK_KEY,
    SOCIAL_TRANSCRIPT_STALE_DAYS,
)
from app.core.clock import utc_now
from app.core.locking import redis_lock
from app.models.social import SocialPost
from app.repositories.social import post_repository
from app.schemas.social import SocialJudgmentBatch

logger = structlog.get_logger(__name__)

SKILL_ID = "social-sentiment"

_LOCK_TTL_SECONDS = 280
#: 喂给 LLM 的口播文稿截断长度（判情绪足够，控 token）
_TRANSCRIPT_CHARS = 800


class SocialJudgmentNotReadyError(Exception):
    """LLM 判断通道暂不可用（celery 捕获后退避重试）。"""


async def judge_pending(session: AsyncSession) -> dict[str, Any]:
    """批量判断待判内容（Celery 每 10 分钟调用）。

    Returns:
        {judged: 判断条数, cleaned: 清理滞留文稿条数}；未获锁时全零。
    """
    async with redis_lock(
        SOCIAL_SENTIMENT_LOCK_KEY, ttl=_LOCK_TTL_SECONDS, blocking=False
    ) as acquired:
        if not acquired:
            logger.info("social_sentiment_lock_busy")
            return {"judged": 0, "cleaned": 0}
        return await _judge_locked(session)


async def _judge_locked(session: AsyncSession) -> dict[str, Any]:
    posts = await post_repository.list_pending_posts(
        session, limit=SOCIAL_JUDGE_BATCH_SIZE
    )
    if not posts:
        cleaned = await _cleanup_stale_transcripts(session)
        await session.commit()
        return {"judged": 0, "cleaned": cleaned}
    rows = await _judge_batch(session, posts)
    if not rows:
        return {"judged": 0, "cleaned": 0}
    await post_repository.upsert_sentiments(session, rows)
    await post_repository.mark_judged(session, [row["post_id"] for row in rows], utc_now())
    await session.commit()
    cleaned = await _cleanup_stale_transcripts(session)
    await session.commit()
    return {"judged": len(rows), "cleaned": cleaned}


async def _judge_batch(
    session: AsyncSession, posts: list[SocialPost]
) -> list[dict[str, Any]]:
    """单批判断：prompt 组装（含热词注入）→ LLM 结构化输出 → 行组装。

    Raises:
        SocialJudgmentNotReadyError: LLM 调用或解析失败（整批下轮重试）。
    """
    from app.agent.core.prompt_renderer import PromptRenderer
    from app.agent.runtime.structured import run_structured
    from app.skills.prompt import load_skill_prompt

    prompt_config = load_skill_prompt(SKILL_ID)
    hotwords = await _load_hotwords(session)
    items = [_post_payload(post) for post in posts]
    user_prompt = PromptRenderer.render(
        prompt_config.user_prompt_template,
        count=len(items),
        items_json=json.dumps(items, ensure_ascii=False),
        hotwords="、".join(hotwords) if hotwords else "（无）",
    )
    try:
        output: SocialJudgmentBatch = await run_structured(
            session, result_type=SocialJudgmentBatch, user_prompt=user_prompt
        )
    except Exception as exc:  # noqa: BLE001 —— LLM/解析失败统一走退避重试
        raise SocialJudgmentNotReadyError(str(exc)) from exc
    return await _to_rows(session, posts, output)


def _post_payload(post: SocialPost) -> dict[str, Any]:
    """待判条目 payload（文稿为判情绪的主要依据，缺失时以标题/文案兜底）。"""
    transcript = post.transcript_text or ""
    return {
        "post_id": post.id,
        "title": post.title or "",
        "caption": (post.caption or "")[:200],
        "topic_tags": post.topic_tags,
        "transcript": transcript[:_TRANSCRIPT_CHARS],
        "transcript_missing": not bool(transcript),
    }


async def _to_rows(
    session: AsyncSession, posts: list[SocialPost], output: SocialJudgmentBatch
) -> list[dict[str, Any]]:
    """LLM 输出 → 待写行：忽略编造 post_id，剔除不在基本表的个股标的。"""
    from app.services.quota.user_llm_service import resolve_llm

    by_id = {post.id: post for post in posts}
    valid_ids = set(by_id)
    valid_codes = await _valid_stock_codes(session)
    cfg, _outlet = await resolve_llm(session, None)
    rows: list[dict[str, Any]] = []
    for item in output.items:
        if item.post_id not in valid_ids:
            logger.warning("social_judgment_unknown_post", post_id=item.post_id)
            continue
        rows.append(
            {
                "post_id": item.post_id,
                "is_relevant": item.relevance,
                "stance": item.stance,
                "confidence": item.confidence,
                "core_arguments": item.core_arguments,
                "targets": [
                    target.model_dump()
                    for target in item.targets
                    if target.target_type != "stock" or target.code in valid_codes
                ],
                "summary": item.summary,
                "model_name": cfg.model_name,
            }
        )
    return rows


async def _valid_stock_codes(session: AsyncSession) -> set[str]:
    """基本表个股代码全集（幻觉标的过滤基准）。"""
    from app.models.stock import StockBasic

    result = await session.execute(select(StockBasic.stock_code))
    return set(result.scalars().all())


async def _load_hotwords(session: AsyncSession) -> list[str]:
    """热词表来自 ASR 渠道配置（官方接口无热词参数，注入判断 prompt 纠偏）。"""
    from app.services.social.asr_service import load_config

    config = await load_config(session)
    return list(config.hotwords) if config else []


async def _cleanup_stale_transcripts(session: AsyncSession) -> int:
    """清理滞留超期的临时文稿（判前失败/反复重试的残留）。"""
    ids = await post_repository.list_stale_transcript_ids(
        session, stale_days=SOCIAL_TRANSCRIPT_STALE_DAYS
    )
    await post_repository.clear_transcripts(session, ids)
    return len(ids)
