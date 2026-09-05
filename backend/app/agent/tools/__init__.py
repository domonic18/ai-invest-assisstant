"""Agent 工具。

按业务域拆分的 LangChain 工具集合；``build_assistant_tools`` 返回助手运行时
使用的完整工具清单。
"""

from langchain_core.tools import BaseTool

from app.agent.tools import db_tools
from app.agent.tools.chain_tools import (
    persist_chain_analysis,
    query_industry_companies,
)
from app.agent.tools.market_tools import (
    get_auction_summary,
    get_market_overview,
    get_sector_fund_flow,
    get_trade_calendar,
)
from app.agent.tools.news_tools import search_news, search_vector_kb
from app.agent.tools.report_tools import (
    download_financial_reports,
    query_financial_reports,
    summarize_financial_report,
)
from app.agent.tools.stock_tools import (
    get_stock_kline,
    get_stock_quote,
    persist_stock_daily_analysis,
    query_financial_data,
)

__all__ = [
    "db_tools",
    "build_assistant_tools",
    "query_industry_companies",
    "persist_chain_analysis",
    "query_financial_reports",
    "download_financial_reports",
    "summarize_financial_report",
    "get_stock_quote",
    "get_stock_kline",
    "query_financial_data",
    "persist_stock_daily_analysis",
    "search_news",
    "search_vector_kb",
    "get_sector_fund_flow",
    "get_market_overview",
    "get_auction_summary",
    "get_trade_calendar",
]


def build_assistant_tools() -> list[BaseTool]:
    """助手工具清单：只读查询工具 + 产业链分析/个股分析持久化工具 + 财报工具。"""
    return [
        get_stock_quote,
        get_stock_kline,
        query_financial_data,
        search_news,
        search_vector_kb,
        get_sector_fund_flow,
        get_market_overview,
        get_auction_summary,
        get_trade_calendar,
        query_industry_companies,
        persist_chain_analysis,
        persist_stock_daily_analysis,
        query_financial_reports,
        download_financial_reports,
        summarize_financial_report,
    ]
