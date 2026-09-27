"""热点主题榜服务：近 24h 高分电报 LLM 聚类 + 库内热度因子拼装。

板块行情仅收盘快照，盘中跑取到的是 T-1，factors.as_of_trade_date 记录
口径供前端标注。input_hash 与当日 session 快照一致时跳过重生成（省 token）。

分层：聚类/热度/词云纯函数在 ``topic_assembly``，快照查询与传导链富化在
``topic_query``，本模块持有并发锁与快照落库编排（get_topics 经此再导出，
API 按模块属性引用）。
"""

import json
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import today_cn
from app.core.locking import redis_lock
from app.repositories.news import topic_repository
from app.services.news import topic_assembly
from app.services.news.topic_query import get_topics  # noqa: F401 —— 再导出：api 引用

logger = structlog.get_logger(__name__)

SKILL_ID = "news-topic"

_LOCK_KEY = "news-topic"
_LOCK_TTL_SECONDS = 900
_MAX_CANDIDATES = 60
_WORDCLOUD_TITLES = 300


async def build_topics(
    session: AsyncSession,
    *,
    session_key: str | None = None,
) -> dict[str, Any]:
    """生成当日指定 session 的热点主题快照（盘中 11:35 / 盘后 16:35）。

    Args:
        session: 数据库会话。
        session_key: intraday|post；缺省按北京时间自动判定（15 点前盘中）。

    Returns:
        {session, trade_date, topics: 主题数, skipped: 是否未生成}；
        未获锁/无候选/同输入已生成/LLM 失败均 skipped=True。
    """
    key = topic_assembly.resolve_session(session_key)
    trade_date = today_cn()
    skipped = {"session": key, "trade_date": trade_date.isoformat(), "topics": 0, "skipped": True}

    async with redis_lock(_LOCK_KEY, ttl=_LOCK_TTL_SECONDS, blocking=False) as acquired:
        if not acquired:
            logger.info("topic_lock_busy")
            return skipped

        rows = await topic_repository.list_recent_candidates(
            session, limit=_MAX_CANDIDATES
        )
        if not rows:
            return skipped
        payload = topic_assembly.trim_to_cap(
            [topic_assembly.candidate_payload(row) for row in rows]
        )

        input_hash = topic_repository.compute_input_hash(
            [p["item_id"] for p in payload]
        )
        existing = await topic_repository.get_snapshot(
            session, trade_date=trade_date, session_key=key
        )
        if existing is not None and existing.input_hash == input_hash:
            return skipped

        from app.skills.prompt import load_skill_prompt

        prompt_config = load_skill_prompt(SKILL_ID)
        from app.agent.core.prompt_renderer import PromptRenderer
        from app.agent.runtime.structured import run_structured
        from app.schemas.news import TopicBatch

        user_prompt = PromptRenderer.render(
            prompt_config.user_prompt_template,
            count=len(payload),
            items_json=json.dumps(payload, ensure_ascii=False),
        )
        try:
            output: TopicBatch = await run_structured(
                session, result_type=TopicBatch, user_prompt=user_prompt
            )
        except Exception as exc:  # noqa: BLE001
            # LLM/解析失败本轮跳过，下轮任务重试（news-score 同款语义）
            logger.warning("topic_llm_failed", error=str(exc))
            return skipped

        valid_keys = {p["item_id"] for p in payload}
        kept: list[Any] = []
        for draft in output.topics:
            if any(i in valid_keys for i in draft.item_ids):
                kept.append(draft)
        # 先按候选 item_ids 过滤草稿，板块因子只查存活主题的板块并集
        sector_names = sorted({n for d in kept for n in d.sector_names})
        factors_by_sector = await topic_repository.sector_factors(
            session, sector_names=sector_names
        )
        max_news_count = max(
            (len([i for i in d.item_ids if i in valid_keys]) for d in kept),
            default=0,
        )
        topics = [
            card
            for d in kept
            if (
                card := topic_assembly.assemble_topic(
                    d, valid_keys, factors_by_sector, max_news_count
                )
            )
        ]
        topics.sort(key=lambda t: t["heat"], reverse=True)

        titles = await topic_repository.list_recent_titles(
            session, limit=_WORDCLOUD_TITLES
        )
        wordcloud = topic_assembly.build_wordcloud(titles)
        await topic_repository.upsert_snapshot(
            session,
            trade_date=trade_date,
            session_key=key,
            topics=topics,
            wordcloud=wordcloud,
            input_hash=input_hash,
        )
        await session.commit()
        logger.info("topic_round_done", session=key, topics=len(topics))
        return {
            "session": key,
            "trade_date": trade_date.isoformat(),
            "topics": len(topics),
            "skipped": False,
        }
