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
FUND_FLOW_MAX_DAYS = 30
_YI = 1e8


def _to_yi(value: Any) -> float | None:
    """金额（元）转亿元，两位小数；空值透传。"""
    return None if value is None else round(float(value) / _YI, 2)


@tool
async def get_stock_fund_flow(stock_code: str, days: int = 10) -> dict[str, Any]:
    """查询个股主力资金流向（近 N 个交易日，单位亿元）：主力净流入及超大单/大单/中单/小单分档。

    Args:
        stock_code: 6 位股票代码，如 "000001"。
        days: 最近交易日数，1-30，默认 10。
    """
    from datetime import timedelta

    from app.core.clock import now_cn
    from app.repositories.market import fund_flow_repository

    days = max(1, min(days, FUND_FLOW_MAX_DAYS))
    end = now_cn().date()
    start = end - timedelta(days=days * 2)  # 自然日窗口放宽，覆盖节假与数据滞后
    async with AsyncSessionLocal() as session:
        rows, _ = await fund_flow_repository.list_paginated(
            session, stock_code=stock_code, start_date=start, end_date=end
        )
    ordered = sorted(rows, key=lambda r: r.trade_date)[-days:]
    return {
        "stock_code": stock_code,
        "unit": "亿元（净流入为正）",
        "items": [
            {
                "trade_date": row.trade_date.isoformat(),
                "main_net_inflow_yi": _to_yi(row.main_net_inflow),
                "super_large_net_yi": _to_yi(row.super_large_net),
                "large_net_yi": _to_yi(row.large_net),
                "medium_net_yi": _to_yi(row.medium_net),
                "small_net_yi": _to_yi(row.small_net),
            }
            for row in ordered
        ],
    }


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


def _parse_trade_date(value: str | None) -> tuple[date | None, str | None]:
    """ISO 日期解析；非法格式返回错误信息。"""
    if value is None:
        return None, None
    try:
        return date.fromisoformat(value), None
    except ValueError:
        return None, "trade_date 须为 YYYY-MM-DD 格式"


@tool
async def get_stock_technical(
    stock_code: str, trade_date: str | None = None
) -> dict[str, Any]:
    """获取单只个股的预计算技术分析文本：通道归属（上升/下降/阻尼运动）、均线关系、支撑/突破/风险三类拐点信号（趋势概要行）、新低/地量/放量、60 日前低支撑、周线形态。

    拐点与通道结论必须直接引用「趋势概要」行的原文，禁止自行估算；
    文本中的关键位与量能判断为预计算指标，可直接作为分析依据。

    Args:
        stock_code: 6 位股票代码，如 "000001"。
        trade_date: 可选历史交易日，ISO 格式如 "2026-09-22"；缺省为最近交易日。
    """
    from app.services.market import index_technical_service, trade_calendar_service

    resolved, error = _parse_trade_date(trade_date)
    if error:
        return {"error": error}

    async with AsyncSessionLocal() as session:
        resolved_date = (
            resolved
            if resolved is not None
            else await trade_calendar_service.resolve_latest_trade_date(session)
        )
        context = await index_technical_service.build_stock_technical_context(
            session, stock_code, resolved_date
        )
    return {"trade_date": resolved_date.isoformat(), "technical_context": context}


@tool
async def get_stock_emotion_context(
    stock_code: str, trade_date: str | None = None
) -> dict[str, Any]:
    """获取单只个股的情绪面上下文：所在行业主力资金净流入与全行业排名、近 5 日累计，个股近 5 日主力资金流，个股当日涨停/连板状态，行业涨停家数，市场涨停结构（总数/首板/连板/最高板）。

    资金净流入为正、净流出为负（单位亿元）；个股未涨停或数据缺失时对应字段为
    null，须如实说明不得臆测。个股连板状态与市场涨停结构互证可判断情绪位置。

    Args:
        stock_code: 6 位股票代码，如 "000001"。
        trade_date: 可选历史交易日，ISO 格式如 "2026-09-22"；缺省为最近交易日。
    """
    from app.services.market import stock_emotion_service, trade_calendar_service

    resolved, error = _parse_trade_date(trade_date)
    if error:
        return {"error": error}

    async with AsyncSessionLocal() as session:
        resolved_date = (
            resolved
            if resolved is not None
            else await trade_calendar_service.resolve_latest_trade_date(session)
        )
        return await stock_emotion_service.build_stock_emotion_context(
            session, stock_code, resolved_date
        )


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
            完全一致（intraday_review / technical_analysis / emotion_analysis /
            key_events / strategy / risk_lines），
            值为对应分区的 Markdown 正文。technical_analysis / strategy /
            risk_lines 须含方法论引用或「无适用方法论」声明，缺失时工具会自动
            补声明并在 warnings 中提示。
    """
    from app.agent.skills.kb_grounding import (
        STOCK_REQUIRED,
        apply_sentinels,
        citation_gaps,
        warning_lines,
    )
    from app.services.admin.llm_config_service import resolve_default_llm
    from app.services.review import stock_daily_analysis_service

    try:
        resolved = date.fromisoformat(trade_date)
    except ValueError:
        return {"error": f"trade_date 格式应为 YYYY-MM-DD，收到：{trade_date}"}

    gaps = citation_gaps(sections, STOCK_REQUIRED)
    if gaps:
        sections = apply_sentinels(sections, gaps)

    async with AsyncSessionLocal() as session:
        cfg = await resolve_default_llm(session)
        analysis = await stock_daily_analysis_service.persist_stock_analysis(
            session,
            stock_code,
            trade_date=resolved,
            contents=sections,
            model=f"{cfg.provider}/{cfg.model_name}",
        )
        result: dict[str, Any] = {
            "stock_code": analysis.stock_code,
            "stock_name": analysis.stock_name,
            "trade_date": analysis.trade_date.isoformat(),
            "section_titles": [section.title for section in analysis.sections],
        }
        if gaps:
            result["warnings"] = warning_lines(gaps)
        result["__event__"] = page_event(
            "stock_daily_analysis.complete",
            stock_code=analysis.stock_code,
            trade_date=analysis.trade_date.isoformat(),
        )
        return result
