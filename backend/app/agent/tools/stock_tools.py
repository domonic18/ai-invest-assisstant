"""个股行情与财务相关助手工具。"""

from typing import Any

from langchain_core.tools import tool

from app.agent.tools import db_tools
from app.core.database import AsyncSessionLocal
from app.services import market as stock_service

KLINE_MAX_DAYS = 120
FINANCIAL_MAX_CODES = 5
FINANCIAL_MAX_PERIODS = 4


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
