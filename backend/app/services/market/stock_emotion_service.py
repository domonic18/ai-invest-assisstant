"""个股情绪面上下文组装（个股每日复盘）。

聚合既有数据源形成单只股票的情绪面视图：所在行业主力资金净流入与排名、
个股主力资金流、个股涨停/连板状态、行业涨停家数与市场涨停结构。
设计原则与指数技术面预计算一致：Python 侧算好确定性问题（排名、累计、
涨停结构），LLM 只负责解读与互证。
"""

from datetime import date, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

_YI = 1e8
_FLOW_DAYS = 5  # 行业与个股资金流统计窗口（交易日）


def _to_yi(value: Any) -> float | None:
    """金额（元）转亿元两位小数，空值透传。"""
    return None if value is None else round(float(value) / _YI, 2)


async def _build_industry_flow(
    session: AsyncSession, industry: str | None, days: int
) -> dict[str, Any] | None:
    """行业主力资金：当日净流入、全行业净流入排名与近 N 日累计。

    行业名为空或资金流表中无该行业时返回 None（不硬凑），由调用方如实披露。
    """
    if not industry:
        return None

    from app.repositories.market import sector_fund_flow_repository

    rows = await sector_fund_flow_repository.list_recent(session, "industry", days)
    series: dict[date, float] = {
        row.trade_date: float(row.main_net_inflow)
        for row in rows
        if row.sector_name == industry and row.main_net_inflow is not None
    }
    if not series:
        return None

    latest_day = max(series)
    latest_rows = [r for r in rows if r.trade_date == latest_day]
    ranked = sorted(
        (
            (float(r.main_net_inflow), r.sector_name)
            for r in latest_rows
            if r.main_net_inflow is not None
        ),
        key=lambda pair: pair[0],
        reverse=True,
    )
    rank = next(
        (i + 1 for i, pair in enumerate(ranked) if pair[1] == industry), None
    )
    return {
        "sector_name": industry,
        "latest_trade_date": latest_day.isoformat(),
        "latest_net_inflow_yi": _to_yi(series[latest_day]),
        "rank": rank,
        "industries_total": len(ranked),
        f"recent_{days}d_net_yi": _to_yi(sum(series.values())),
    }


async def _build_stock_flow(
    session: AsyncSession, stock_code: str, trade_date: date, days: int
) -> dict[str, Any] | None:
    """个股近 N 个交易日主力净流入序列（亿元，升序）。"""
    from app.repositories.market import fund_flow_repository

    rows, _ = await fund_flow_repository.list_paginated(
        session,
        stock_code=stock_code,
        start_date=trade_date - timedelta(days=days * 3),
        end_date=trade_date,
        page_size=days,
    )
    ordered = sorted(rows, key=lambda r: r.trade_date)[-days:]
    if not ordered:
        return None
    return {
        "items": [
            {
                "trade_date": row.trade_date.isoformat(),
                "main_net_inflow_yi": _to_yi(row.main_net_inflow),
            }
            for row in ordered
        ]
    }


async def build_stock_emotion_context(
    session: AsyncSession, stock_code: str, trade_date: date
) -> dict[str, Any]:
    """构建个股情绪面上下文（工具 ``get_stock_emotion_context`` 的服务层）。

    Args:
        session: 数据库会话。
        stock_code: 6 位股票代码。
        trade_date: 交易日（涨停池与资金流的统计基准日）。

    Returns:
        dict：industry / industry_flow / stock_flow / stock_limit_up /
        industry_limit_up_count / market_emotion；任一数据源缺失置 null，不抛错。
    """
    from app.services.market import limit_pool_service, stock_service

    stock = await stock_service.get_stock_by_code(session, stock_code)
    industry = (
        stock.industry_level_2 or stock.industry_level_1 if stock else None
    ) or None

    pool = await limit_pool_service.get_limit_up(session, trade_date)
    stock_item = next(
        (item for item in pool.items if item.stock_code == stock_code), None
    )
    stock_limit_up = (
        {
            "consecutive_boards": stock_item.consecutive_boards,
            "first_seal_time": stock_item.first_seal_time,
            "last_seal_time": stock_item.last_seal_time,
            "broken_limit_count": stock_item.broken_limit_count,
            "limit_status": stock_item.limit_status,
            "seal_type": stock_item.seal_type,
            "pool_industry": stock_item.industry,
        }
        if stock_item
        else None
    )

    return {
        "trade_date": trade_date.isoformat(),
        "industry": industry,
        "industry_flow": await _build_industry_flow(session, industry, _FLOW_DAYS),
        "stock_flow": await _build_stock_flow(
            session, stock_code, trade_date, _FLOW_DAYS
        ),
        "stock_limit_up": stock_limit_up,
        "industry_limit_up_count": (
            sum(1 for item in pool.items if item.industry == industry)
            if industry
            else None
        ),
        "market_emotion": {
            "total": pool.total,
            "first_board": pool.first_board,
            "continuous": pool.continuous,
            "max_boards": pool.max_boards,
        }
        if pool.total
        else None,
    }
