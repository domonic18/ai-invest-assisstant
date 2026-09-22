"""新闻与知识库检索相关助手工具。"""

from typing import Any

from langchain_core.tools import tool

from app.agent.tools import db_tools
from app.agent.tools.market_tools import _parse_trade_date
from app.core.database import AsyncSessionLocal
from app.repositories.market import telegraph_repository

NEWS_MAX_DAYS = 180
NEWS_MAX_ROWS = 30
KB_MAX_ROWS = 10
IMPORTANT_NEWS_CONTENT_MAX = 160


@tool
async def search_news(
    keyword: str,
    days: int = 30,
    limit: int = 15,
    doc_types: list[str] | None = None,
) -> list[dict[str, Any]]:
    """按关键词检索近期新闻/公告/研报的标题与摘要。

    Args:
        keyword: 检索关键词，如 "半导体" 或股票名称。
        days: 回溯天数，1-180，默认 30。
        limit: 返回条数，1-30，默认 15。
        doc_types: 文档类型过滤，可选值 news / announcement / report。
    """
    days = max(1, min(days, NEWS_MAX_DAYS))
    limit = max(1, min(limit, NEWS_MAX_ROWS))
    async with AsyncSessionLocal() as session:
        return await db_tools.search_news(session, keyword, days, limit, doc_types)


@tool
async def search_news_by_date(
    start_date: str, end_date: str, limit: int = 30
) -> list[dict[str, Any]] | dict[str, Any]:
    """按发布日期区间检索新闻/公告/研报的标题与摘要（不限关键词，按时间倒序）。

    Args:
        start_date: 起始日期（含），ISO 格式如 "2026-09-03"。
        end_date: 结束日期（含），ISO 格式如 "2026-09-04"。
        limit: 返回条数，1-30，默认 30。
    """
    start, start_error = _parse_trade_date(start_date)
    end, end_error = _parse_trade_date(end_date)
    if start_error or end_error or start is None or end is None:
        return {"error": "start_date/end_date 均须为 YYYY-MM-DD 格式"}
    limit = max(1, min(limit, NEWS_MAX_ROWS))
    async with AsyncSessionLocal() as session:
        return await db_tools.search_news_by_date(session, start, end, limit)


@tool
async def get_important_news(trade_date: str) -> dict[str, Any]:
    """获取当日重点要闻（财联社电报 AI 评分 ≥70，按评分降序），供消息面复盘取数。

    Args:
        trade_date: 交易日期，ISO 格式如 "2026-09-17"。
    """
    day, error = _parse_trade_date(trade_date)
    if error or day is None:
        return {"error": "trade_date 须为 YYYY-MM-DD 格式"}
    async with AsyncSessionLocal() as session:
        rows = await telegraph_repository.list_top_telegraph(session, day)

    items: list[dict[str, Any]] = []
    for telegraph, score, score_detail in rows:
        reason = ""
        if isinstance(score_detail, dict):
            reason = str(score_detail.get("reason") or "")
        items.append(
            {
                "title": telegraph.title,
                "content": (telegraph.content or "")[:IMPORTANT_NEWS_CONTENT_MAX],
                "score": score,
                "reason": reason,
                "publish_time": telegraph.publish_time.isoformat(),
                "stock_codes": telegraph.stock_codes or [],
            }
        )
    note = (
        f"共 {len(items)} 条重点要闻（评分≥70）。"
        if items
        else "当日无评分达标的重点要闻（≥70 分），消息面应如实说明，不得用普通消息凑数。"
    )
    return {"trade_date": day.isoformat(), "items": items, "note": note}


@tool
async def search_vector_kb(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """按关键词检索研报/财报 PDF 全文，返回标题与内容片段；无命中时回退研报标题/摘要检索。

    Args:
        query: 检索语句，如 "光模块 CPO 产能"。
        limit: 返回条数，1-10，默认 5。
    """
    limit = max(1, min(limit, KB_MAX_ROWS))
    async with AsyncSessionLocal() as session:
        return await db_tools.search_vector_kb(session, query, limit)
