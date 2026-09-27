"""热点主题读取层：当日快照查询 + 传导链标的读取时富化。

快照落库在 ``topic_service``，聚类拼装纯函数在 ``topic_assembly``。
"""

import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import today_cn
from app.repositories.market.stock_repository import StockRepository
from app.repositories.news import topic_repository
from app.services.market import stock_service

# 传导链标的：LLM 自由文本里的 6 位代码（可带 sh/sz/bj 前缀）
_CHAIN_STOCK_CODE_RE = re.compile(r"^(?:sh|sz|bj)?(\d{6})$", re.IGNORECASE)


async def get_topics(
    session: AsyncSession,
    *,
    session_key: str = "post",
) -> dict[str, Any]:
    """读取当日指定 session 的主题快照（无快照返回空列表，不触发生成）。"""
    trade_date = today_cn()
    snapshot = await topic_repository.get_snapshot(
        session, trade_date=trade_date, session_key=session_key
    )
    topics = list(snapshot.topics or []) if snapshot else []
    if topics:
        await _enrich_chain_stocks(session, topics)
    return {
        "trade_date": trade_date.isoformat(),
        "session": session_key,
        "topics": topics,
        "wordcloud": list(snapshot.wordcloud or []) if snapshot else [],
        "generated_at": snapshot.generated_at if snapshot else None,
    }


async def _enrich_chain_stocks(
    session: AsyncSession, topics: list[dict[str, Any]]
) -> None:
    """读取时富化传导链标的：LLM 自由文本（代码或简称）→ {name, code, change_pct}。

    快照 JSONB 存的是原文；涨跌幅必须读时取（快照盘后生成，涨幅随行情变化）。
    无法解析为 A 股标的的原文保留为纯文本名（code=None，前端不加链接）。
    """
    raw_set = {
        raw
        for topic in topics
        for step in topic.get("chain", [])
        for raw in step.get("stocks", [])
    }
    if not raw_set:
        return

    code_by_raw: dict[str, str] = {}
    names: list[str] = []
    for raw in raw_set:
        match = _CHAIN_STOCK_CODE_RE.match(raw.strip())
        if match:
            code_by_raw[raw] = match.group(1)
        else:
            names.append(raw)
    if names:
        name_map = await StockRepository(session).get_codes_by_names(names)
        for raw in names:
            if raw in name_map:
                code_by_raw[raw] = name_map[raw]

    snapshots = await stock_service.batch_quote_snapshot(
        session, list(dict.fromkeys(code_by_raw.values()))
    )
    for topic in topics:
        for step in topic.get("chain", []):
            enriched: list[dict[str, Any]] = []
            for raw in step.get("stocks", []):
                code = code_by_raw.get(raw)
                snap = snapshots.get(code) if code else None
                enriched.append(
                    {
                        "name": snap["name"] if snap else raw,
                        "code": code,
                        "change_pct": snap["change_pct"] if snap else None,
                    }
                )
            step["stocks"] = enriched
