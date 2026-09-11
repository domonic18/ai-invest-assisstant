"""Agent 工具。

按业务域拆分的 LangChain 工具集合；``build_assistant_tools`` 返回助手运行时
使用的完整工具清单。
"""

from typing import Any, cast

from langchain_core.tools import BaseTool

from app.agent.tools import db_tools
from app.agent.tools.anomaly_tools import (
    persist_sector_anomaly_attribution,
    persist_stock_anomaly_attribution,
)
from app.agent.tools.chain_tools import (
    persist_chain_analysis,
    query_industry_companies,
)
from app.agent.tools.dragon_tiger_tools import get_dragon_tiger
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
    get_stock_fund_flow,
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
    "get_stock_fund_flow",
    "get_dragon_tiger",
    "persist_sector_anomaly_attribution",
    "persist_stock_anomaly_attribution",
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
        get_stock_fund_flow,
        get_dragon_tiger,
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
        persist_sector_anomaly_attribution,
        persist_stock_anomaly_attribution,
        collect_market_data,
        query_financial_reports,
        download_financial_reports,
        summarize_financial_report,
    ]


def _mcp_client_config(row: Any) -> dict[str, Any]:
    """把 McpServerConfig 行映射为 langchain-mcp-adapters 连接配置。"""
    if row.transport_type == "stdio":
        return {
            "transport": "stdio",
            "command": row.command,
            "args": list(row.args or []),
            "env": dict(row.env or {}),
        }
    return {
        "transport": "streamable_http" if row.transport_type == "http" else "sse",
        "url": row.url,
        "headers": dict(row.headers or {}),
        "timeout": row.timeout_seconds,
    }


async def build_mcp_tools() -> list[BaseTool]:
    """后台已启用 MCP 服务的工具清单（langchain-mcp-adapters 适配）。

    每个配置独立建客户端：单服务失败只记日志，不影响其余服务注入；工具名
    冲突保留先注册的并跳过后者。返回的工具在每次调用时新建会话（不维持
    长连接），故 agent 重建（``reset_assistant_agent()``）即完成配置热更。
    """
    import structlog
    from sqlalchemy import select

    from app.core.database import AsyncSessionLocal
    from app.models.mcp_server import McpServerConfig

    logger = structlog.get_logger(__name__)
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(McpServerConfig)
                .where(McpServerConfig.enabled.is_(True))
                .order_by(McpServerConfig.id.asc())
            )
        ).scalars().all()
    if not rows:
        return []

    from langchain_mcp_adapters.client import MultiServerMCPClient
    from langchain_mcp_adapters.sessions import Connection

    collected: list[BaseTool] = []
    seen: set[str] = set()
    for row in rows:
        try:
            row_tools = await MultiServerMCPClient(
                {row.name: cast("Connection", _mcp_client_config(row))}
            ).get_tools()
        except BaseException as exc:  # noqa: BLE001 - 单服务失败不阻断其余服务
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            logger.warning("mcp_tools_load_failed", server=row.name, error=str(exc))
            continue
        for tool in row_tools:
            if tool.name in seen:
                logger.warning(
                    "mcp_tool_name_conflict_skipped", server=row.name, tool=tool.name
                )
                continue
            seen.add(tool.name)
            collected.append(tool)
    logger.info(
        "mcp_tools_loaded",
        servers=[row.name for row in rows],
        n_tools=len(collected),
    )
    return collected
