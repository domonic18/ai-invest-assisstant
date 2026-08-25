"""助手只读数据工具：LangChain ``@tool`` 包装既有 service / db_tools。

全部为只读查询；包装层统一做行数/天数上限裁剪，防止单次工具输出撑爆
模型上下文。写操作类工具（触发采集/AI 分析等）在 Phase 4 配合 HITL 引入。
"""

from datetime import date
from typing import Any

from langchain_core.tools import BaseTool, tool

from app.agent.tools import db_tools
from app.core.database import AsyncSessionLocal
from app.services import (
    auction_service,
    index_quotation_service,
    sector_fund_flow_service,
    stock_service,
)
from app.services import market_stats_service as market_stats_svc

KLINE_MAX_DAYS = 120
FINANCIAL_MAX_CODES = 5
FINANCIAL_MAX_PERIODS = 4
NEWS_MAX_DAYS = 180
NEWS_MAX_ROWS = 30
KB_MAX_ROWS = 10
SECTOR_MAX_DAYS = 60
SECTOR_TOP_N = 10
AUCTION_MAX_DAYS = 30


@tool
async def get_stock_quote(stock_code: str) -> dict[str, Any] | None:
    """获取个股最新行情快照：现价、涨跌幅、成交量/额、总市值，Redis 实时缺失时回退最新日 K。

    Args:
        stock_code: 6 位股票代码，如 "000001"（平安银行）。
    """
    async with AsyncSessionLocal() as session:
        return await stock_service.get_stock_quote(session, stock_code)


@tool
async def get_stock_kline(stock_code: str, limit: int = 30) -> list[dict[str, Any]]:
    """查询个股近期日 K 线（日期、开高低收、成交量、涨跌幅），按交易日倒序。

    Args:
        stock_code: 6 位股票代码，如 "000001"。
        limit: 返回条数，1-120，默认 30。
    """
    limit = max(1, min(limit, KLINE_MAX_DAYS))
    async with AsyncSessionLocal() as session:
        return await db_tools.query_stock_kline(session, stock_code, limit)


@tool
async def query_financial_data(
    stock_codes: list[str], periods: int = 3
) -> list[dict[str, Any]]:
    """批量查询股票核心财务指标：最新报告期毛利率、营收同比、研发占比、应收账款周转。

    Args:
        stock_codes: 6 位股票代码列表，最多 5 只。
        periods: 参考期数，默认 3。
    """
    codes = stock_codes[:FINANCIAL_MAX_CODES]
    periods = max(1, min(periods, FINANCIAL_MAX_PERIODS))
    async with AsyncSessionLocal() as session:
        return await db_tools.query_financial_data(session, codes, periods)


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


def _trim_sector_flow(response: Any, top_n: int) -> dict[str, Any]:
    """板块资金流响应裁剪：只保留净流入绝对值 Top N 板块的区间累计与最新值。"""
    dates = [d.isoformat() for d in response.dates]
    rows: list[dict[str, Any]] = []
    for sector in response.sectors:
        values = [v for v in sector.values if v is not None]
        period_net = round(sum(sector.values[i] or 0.0 for i in range(len(dates))), 2)
        rows.append(
            {
                "code": sector.code,
                "name": sector.name,
                "period_net_inflow_yi": period_net,
                "latest_yi": values[-1] if values else None,
            }
        )
    rows.sort(key=lambda r: abs(r["period_net_inflow_yi"]), reverse=True)
    return {
        "dates": [dates[0], dates[-1]] if dates else [],
        "unit": "亿元（主力净流入）",
        "sectors": rows[:top_n],
    }


@tool
async def get_sector_fund_flow(
    sector_type: str = "industry", days: int = 20, top: int = 10
) -> dict[str, Any]:
    """查询板块主力资金净流入排行（区间累计与最新一日，单位亿元）。当前仅支持行业板块。

    Args:
        sector_type: 板块类型，当前仅 "industry"。
        days: 统计区间交易日数，1-60，默认 20。
        top: 返回板块数，默认 10。
    """
    days = max(1, min(days, SECTOR_MAX_DAYS))
    async with AsyncSessionLocal() as session:
        response = await sector_fund_flow_service.get_sector_flow_trend(
            session, sector_type, days
        )
    return _trim_sector_flow(response, top)


@tool
async def get_market_overview(trade_date: str | None = None) -> dict[str, Any]:
    """获取大盘概览：四大指数行情 + 全市场涨跌家数、成交额（含环比）、涨停/跌停家数与情绪温度。

    Args:
        trade_date: 可选历史交易日，ISO 格式如 "2026-08-21"；缺省为最新交易日。
    """
    resolved: date | None = None
    if trade_date:
        try:
            resolved = date.fromisoformat(trade_date)
        except ValueError:
            return {"error": "trade_date 须为 YYYY-MM-DD 格式"}

    async with AsyncSessionLocal() as session:
        stats = await market_stats_svc.get_market_stats(session, resolved)
        quotes = await index_quotation_service.get_index_quotes(session, resolved)

    return {
        "market_stats": stats.model_dump(mode="json"),
        "index_quotes": [
            q.model_dump(mode="json", exclude={"trend"}) for q in quotes
        ],
    }


@tool
async def get_auction_summary(days: int = 5) -> dict[str, Any]:
    """查询指数集合竞价成交额趋势（单位亿元），反映开盘前资金活跃度。

    Args:
        days: 最近交易日数，1-30，默认 5。
    """
    days = max(1, min(days, AUCTION_MAX_DAYS))
    async with AsyncSessionLocal() as session:
        response = await auction_service.get_index_auction_trend(session, days=days)

    dates = [d.isoformat() for d in response.dates]
    series = [
        {
            "code": s.code,
            "name": s.name,
            "values_yi": s.values,
            "latest_yi": next((v for v in reversed(s.values) if v is not None), None),
        }
        for s in response.series
    ]
    return {"dates": dates, "series": series}


def build_assistant_tools() -> list[BaseTool]:
    """Phase 1 工具清单（8 个只读工具）。"""
    return [
        get_stock_quote,
        get_stock_kline,
        query_financial_data,
        search_news,
        search_vector_kb,
        get_sector_fund_flow,
        get_market_overview,
        get_auction_summary,
    ]
