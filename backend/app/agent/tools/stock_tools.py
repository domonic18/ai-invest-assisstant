"""个股行情与财务相关助手工具。"""

from datetime import date
from typing import Any

from langchain_core.tools import tool

from app.agent.tools import db_tools
from app.agent.tools.page_event import page_event
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


@tool
async def persist_stock_daily_analysis(
    stock_code: str, trade_date: str, sections: dict[str, str]
) -> dict[str, Any]:
    """持久化个股每日 AI 分析结果到数据库，个股页 AI 复盘会自动刷新展示。

    Args:
        stock_code: 6 位股票代码，如 "600519"（贵州茅台）。
        trade_date: 交易日（YYYY-MM-DD）。
        sections: 分析分区内容字典，键必须与 stock-daily-analysis SKILL 输出 Schema
            完全一致（intraday_review / key_events / strategy / risk_lines），
            值为对应分区的 Markdown 正文。
    """
    from app.services.admin.llm_config_service import resolve_default_llm
    from app.services.review import stock_daily_analysis_service

    try:
        resolved = date.fromisoformat(trade_date)
    except ValueError:
        return {"error": f"trade_date 格式应为 YYYY-MM-DD，收到：{trade_date}"}

    async with AsyncSessionLocal() as session:
        cfg = await resolve_default_llm(session)
        analysis = await stock_daily_analysis_service.persist_stock_analysis(
            session,
            stock_code,
            trade_date=resolved,
            contents=sections,
            model=f"{cfg.provider}/{cfg.model_name}",
        )
        return {
            "stock_code": analysis.stock_code,
            "stock_name": analysis.stock_name,
            "trade_date": analysis.trade_date.isoformat(),
            "section_titles": [section.title for section in analysis.sections],
            "__event__": page_event(
                "stock_daily_analysis.complete",
                stock_code=analysis.stock_code,
                trade_date=analysis.trade_date.isoformat(),
            ),
        }
