"""助手数据工具（兼容 facade）。

工具实现已按域拆分到 ``app.agent.tools.*``；本模块保留向后兼容的聚合导出，
供现有调用方与测试逐步迁移。
"""

# ruff: noqa: F401

from app.agent.tools import build_assistant_tools, db_tools
from app.agent.tools.chain_tools import (
    INDUSTRY_COMPANIES_MAX_LIMIT,
    persist_chain_analysis,
    query_industry_companies,
)
from app.agent.tools.market_tools import (
    AUCTION_MAX_DAYS,
    SECTOR_MAX_DAYS,
    SECTOR_TOP_N,
    get_auction_summary,
    get_market_overview,
    get_sector_fund_flow,
)
from app.agent.tools.news_tools import (
    KB_MAX_ROWS,
    NEWS_MAX_DAYS,
    NEWS_MAX_ROWS,
    search_news,
    search_vector_kb,
)
from app.agent.tools.report_tools import (
    FINANCIAL_REPORT_MAX_LIMIT,
    download_financial_reports,
    query_financial_reports,
    summarize_financial_report,
)
from app.agent.tools.stock_tools import (
    FINANCIAL_MAX_CODES,
    FINANCIAL_MAX_PERIODS,
    KLINE_MAX_DAYS,
    get_stock_kline,
    get_stock_quote,
    query_financial_data,
)
from app.core.database import AsyncSessionLocal
from app.services import (
    auction_service,
    index_quotation_service,
    sector_fund_flow_service,
    stock_service,
)
from app.services import market_stats_service as market_stats_svc

__all__ = [
    "AsyncSessionLocal",
    "build_assistant_tools",
    "query_industry_companies",
    "persist_chain_analysis",
    "query_financial_reports",
    "download_financial_reports",
    "summarize_financial_report",
    "get_stock_quote",
    "get_stock_kline",
    "query_financial_data",
    "search_news",
    "search_vector_kb",
    "get_sector_fund_flow",
    "get_market_overview",
    "get_auction_summary",
    "db_tools",
    "stock_service",
    "market_stats_svc",
    "sector_fund_flow_service",
    "index_quotation_service",
    "auction_service",
    "INDUSTRY_COMPANIES_MAX_LIMIT",
    "FINANCIAL_REPORT_MAX_LIMIT",
    "KLINE_MAX_DAYS",
    "FINANCIAL_MAX_CODES",
    "FINANCIAL_MAX_PERIODS",
    "NEWS_MAX_DAYS",
    "NEWS_MAX_ROWS",
    "KB_MAX_ROWS",
    "SECTOR_MAX_DAYS",
    "SECTOR_TOP_N",
    "AUCTION_MAX_DAYS",
]
