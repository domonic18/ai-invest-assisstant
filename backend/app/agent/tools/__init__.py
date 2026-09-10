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
    collect_market_data,
    get_auction_summary,
    get_index_technical,
    get_limit_up_ladder,
    get_limit_up_pool,
    get_market_overview,
    get_sector_fund_flow,
    get_sector_overview,
    get_trade_calendar,
    persist_limit_up_attribution,
    persist_market_review,
)
from app.agent.tools.news_tools import search_news, search_news_by_date, search_vector_kb
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
    "get_sector_overview",
    "get_market_overview",
    "get_auction_summary",
    "get_trade_calendar",
    "get_limit_up_ladder",
    "get_limit_up_pool",
    "get_index_technical",
    "persist_market_review",
    "persist_limit_up_attribution",
    "collect_market_data",
    "search_news_by_date",
]


def build_assistant_tools() -> list[BaseTool]:
    """助手工具清单：只读查询工具 + 产业链分析/个股分析/大盘复盘/涨停归因持久化工具 + 财报工具 + 行情补采。"""
    return [
        get_stock_quote,
        get_stock_kline,
        query_financial_data,
        search_news,
        search_news_by_date,
        search_vector_kb,
        get_sector_fund_flow,
        get_sector_overview,
        get_market_overview,
        get_limit_up_ladder,
        get_limit_up_pool,
        get_index_technical,
        get_auction_summary,
        get_trade_calendar,
        query_industry_companies,
        persist_chain_analysis,
        persist_stock_daily_analysis,
        persist_market_review,
        persist_limit_up_attribution,
        collect_market_data,
        query_financial_reports,
        download_financial_reports,
        summarize_financial_report,
    ]


async def build_mcp_tools() -> list[BaseTool]:
    """后台已启用 MCP 服务的工具清单（Phase 2 接入点）。

    当前仅统计 enabled 配置数并返回空清单；Phase 2 在此用
    ``langchain-mcp-adapters``（load_mcp_tools）将各 enabled server 的工具
    适配为 LangChain 工具。注意：助手 agent 是缓存单例，配置变更后须
    ``reset_assistant_agent()`` 使其重建。
    """
    import structlog
    from sqlalchemy import select

    from app.core.database import AsyncSessionLocal
    from app.models.mcp_server import McpServerConfig

    logger = structlog.get_logger(__name__)
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(McpServerConfig).where(McpServerConfig.enabled.is_(True))
            )
        ).scalars().all()
    if rows:
        logger.info(
            "mcp_tools_injection_pending",
            servers=[row.name for row in rows],
            hint="Phase 2: langchain-mcp-adapters 接入后返回真实工具",
        )
    return []
