"""新闻与知识库检索相关助手工具。"""

from typing import Any

from langchain_core.tools import tool

from app.agent.tools import db_tools
from app.core.database import AsyncSessionLocal

NEWS_MAX_DAYS = 180
NEWS_MAX_ROWS = 30
KB_MAX_ROWS = 10


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
async def search_vector_kb(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """检索研报知识库（全文检索），返回研报标题与内容片段；ES 不可用时自动回退研报标题检索。

    Args:
        query: 检索语句，如 "光模块 CPO 产能"。
        limit: 返回条数，1-10，默认 5。
    """
    limit = max(1, min(limit, KB_MAX_ROWS))
    async with AsyncSessionLocal() as session:
        return await db_tools.search_vector_kb(session, query, limit)
