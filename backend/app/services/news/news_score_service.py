"""资讯 AI 重要度分级服务：多源批量评分，写入 news_ai_score 标注表。

定时路径（news-score 任务）专用；评分源注册制——新增资讯源在此登记
取批函数即自动纳入分级（源表零改动，标注按 (source, item_id) 另存）。
"""

import json
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.locking import redis_lock
from app.models.news_telegraph import NewsTelegraph
from app.repositories.news import ai_score_repository
from app.schemas.news import NewsScoreBatch

logger = structlog.get_logger(__name__)

SKILL_ID = "news-score"
SOURCE_TELEGRAPH = ai_score_repository.SOURCE_TELEGRAPH

_LOCK_KEY = "news-ai-score"
_LOCK_TTL_SECONDS = 280
_BATCH_SIZE = 20
_MAX_BATCHES_PER_SOURCE = 3
_CONTENT_CHARS = 500

ScoredPayload = list[dict[str, Any]]
Batcher = Callable[[AsyncSession, int], Awaitable[ScoredPayload]]

# 评分源注册表：source -> 取批函数（返回待评 payload，空列表表示无待评）。
# 新增资讯源时在此登记一行即可纳入定时分级。
_SOURCE_BATCHERS: dict[str, Batcher] = {}


def register_source(source: str, batcher: Batcher) -> None:
    """登记一个评分源（模块注册用，运行期一般不动态调用）。"""
    _SOURCE_BATCHERS[source] = batcher


async def _batch_telegraph(session: AsyncSession, limit: int) -> ScoredPayload:
    rows = await ai_score_repository.list_unscored_telegraph(
        session, limit=limit
    )
    return [_telegraph_payload(row) for row in rows]


def _telegraph_payload(row: NewsTelegraph) -> dict[str, Any]:
    content = row.content or ""
    return {
        "source": SOURCE_TELEGRAPH,
        "item_id": str(row.cls_msg_id),
        "title": row.title,
        "content": content[:_CONTENT_CHARS],
        "category": row.category,
        "stock_codes": row.stock_codes or [],
    }


register_source(SOURCE_TELEGRAPH, _batch_telegraph)


async def score_pending(session: AsyncSession) -> dict[str, Any]:
    """对所有注册源批量评分未分级资讯（Celery 每 5 分钟调用）。

    Returns:
        {scored: 总写入条数, by_source: {source: 条数}}；未获锁时全零。
    """
    by_source: dict[str, int] = {}
    async with redis_lock(_LOCK_KEY, ttl=_LOCK_TTL_SECONDS, blocking=False) as acquired:
        if not acquired:
            logger.info("news_score_lock_busy")
            return {"scored": 0, "by_source": by_source}

        from app.skills.prompt import load_skill_prompt

        prompt_config = load_skill_prompt(SKILL_ID)
        for source, batcher in _SOURCE_BATCHERS.items():
            scored = 0
            for _ in range(_MAX_BATCHES_PER_SOURCE):
                batch = await batcher(session, _BATCH_SIZE)
                if not batch:
                    break
                try:
                    rows = await _score_batch(session, prompt_config, batch)
                except Exception as exc:  # noqa: BLE001
                    # LLM/解析失败整批跳过，下轮任务重试；不影响其他源
                    logger.warning(
                        "news_score_batch_failed", source=source, error=str(exc)
                    )
                    break
                if not rows:
                    break
                scored += await ai_score_repository.upsert_scores(session, rows)
                await session.commit()
            if scored:
                by_source[source] = scored
                logger.info("news_score_source_done", source=source, scored=scored)
    return {"scored": sum(by_source.values()), "by_source": by_source}


async def _score_batch(
    session: AsyncSession,
    prompt_config: Any,
    batch: ScoredPayload,
) -> list[dict[str, Any]]:
    """单批评分：LLM 结构化输出 -> 过滤幻觉项 -> 待写行。"""
    from app.agent.core.prompt_renderer import PromptRenderer
    from app.agent.runtime.structured import run_structured

    user_prompt = PromptRenderer.render(
        prompt_config.user_prompt_template,
        count=len(batch),
        items_json=json.dumps(batch, ensure_ascii=False),
    )
    output: NewsScoreBatch = await run_structured(
        session, result_type=NewsScoreBatch, user_prompt=user_prompt
    )
    valid_keys = {(item["source"], item["item_id"]) for item in batch}
    now_rows: list[dict[str, Any]] = []
    for item in output.items:
        if (item.source, item.item_id) not in valid_keys:
            logger.warning(
                "news_score_hallucinated_item", source=item.source, item_id=item.item_id
            )
            continue
        now_rows.append(
            {
                "source": item.source,
                "item_id": item.item_id,
                "score": item.score,
                "score_detail": {"reason": item.reason},
            }
        )
    return now_rows
