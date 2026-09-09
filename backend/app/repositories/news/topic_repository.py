"""热点主题仓储：候选电报、板块资金因子与快照 upsert。"""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import String, cast, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import NEWS_SOURCE_TELEGRAPH
from app.models.capital_fund_flow_sector import SectorFundFlow
from app.models.news_ai_score import NewsAiScore
from app.models.news_telegraph import NewsTelegraph
from app.models.news_topic_snapshot import NewsTopicSnapshot

SOURCE_TELEGRAPH = NEWS_SOURCE_TELEGRAPH


async def list_recent_candidates(
    session: AsyncSession,
    *,
    hours: int = 24,
    min_score: int = 40,
    limit: int = 60,
) -> list[Any]:
    """取近 hours 小时 score≥min_score 的电报（新消息优先），供主题聚类。"""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    stmt = (
        select(NewsTelegraph, NewsAiScore.score)
        .join(
            NewsAiScore,
            (NewsAiScore.source == SOURCE_TELEGRAPH)
            & (NewsAiScore.item_id == cast(NewsTelegraph.cls_msg_id, String)),
        )
        .where(NewsAiScore.score >= min_score, NewsTelegraph.publish_time > since)
        .order_by(NewsTelegraph.publish_time.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.all())


async def list_recent_titles(
    session: AsyncSession,
    *,
    hours: int = 24,
    limit: int = 300,
) -> list[str | None]:
    """近 hours 小时电报标题（词云词频统计，不筛分数）。"""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    stmt = (
        select(NewsTelegraph.title)
        .where(NewsTelegraph.publish_time > since)
        .order_by(NewsTelegraph.publish_time.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return [row[0] for row in result.all()]


async def sector_factors(
    session: AsyncSession,
    *,
    sector_names: list[str],
) -> dict[str, dict[str, Any]]:
    """按板块名取最近交易日因子：{name: {trade_date, change_pct, main_net_inflow}}。

    板块行情仅收盘快照：盘中跑取到的是 T-1，由调用方按 as_of_trade_date 标注。
    """
    if not sector_names:
        return {}
    stmt = (
        select(
            SectorFundFlow.sector_name,
            SectorFundFlow.trade_date,
            SectorFundFlow.change_pct,
            SectorFundFlow.main_net_inflow,
        )
        .distinct(SectorFundFlow.sector_name)
        .where(SectorFundFlow.sector_name.in_(sector_names))
        .order_by(SectorFundFlow.sector_name, SectorFundFlow.trade_date.desc())
    )
    result = await session.execute(stmt)
    return {
        row.sector_name: {
            "trade_date": row.trade_date,
            "change_pct": row.change_pct,
            "main_net_inflow": row.main_net_inflow,
        }
        for row in result.all()
    }


def compute_input_hash(item_ids: list[str]) -> str:
    """候选条目摘要哈希：同输入跳过重生成（token 成本控制）。"""
    return hashlib.sha256(",".join(item_ids).encode()).hexdigest()


async def upsert_snapshot(
    session: AsyncSession,
    *,
    trade_date: Any,
    session_key: str,
    topics: list[dict[str, Any]],
    wordcloud: list[dict[str, Any]],
    input_hash: str,
) -> None:
    """按 PK(trade_date, session) upsert 快照（不 commit）。"""
    now = datetime.now(timezone.utc)
    stmt = pg_insert(NewsTopicSnapshot).values(
        trade_date=trade_date,
        session=session_key,
        topics=topics,
        wordcloud=wordcloud,
        input_hash=input_hash,
        generated_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["trade_date", "session"],
        set_={
            "topics": stmt.excluded.topics,
            "wordcloud": stmt.excluded.wordcloud,
            "input_hash": stmt.excluded.input_hash,
            "generated_at": stmt.excluded.generated_at,
        },
    )
    await session.execute(stmt)


async def get_snapshot(
    session: AsyncSession,
    *,
    trade_date: Any,
    session_key: str,
) -> NewsTopicSnapshot | None:
    """取当日指定 session 的快照。"""
    stmt = select(NewsTopicSnapshot).where(
        NewsTopicSnapshot.trade_date == trade_date,
        NewsTopicSnapshot.session == session_key,
    )
    result = await session.execute(stmt)
    return result.scalars().first()
