"""市场行情与板块资金流向相关助手工具。"""

from datetime import date
from typing import Any

from langchain_core.tools import tool

from app.core.database import AsyncSessionLocal
from app.services import (
    auction_service,
    index_quotation_service,
    sector_fund_flow_service,
)
from app.services import market_stats_service as market_stats_svc

SECTOR_MAX_DAYS = 60
SECTOR_TOP_N = 10
AUCTION_MAX_DAYS = 30


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
