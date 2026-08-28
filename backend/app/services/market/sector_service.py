"""板块热力图 + 资金流 TOP + 领涨板块。

只读 ``capital_fund_flow_sector``；领涨板块的涨停家数与代表股通过 ``limit_pool_service``
派生（同口径，避免数据来源错配）。
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.capital_fund_flow_sector import SectorFundFlow
from app.schemas.market import (
    LeadingSectorItem,
    SectorFlowItem,
    SectorHeatItem,
    SectorOverviewResponse,
)
from app.services.market import limit_pool_service, trade_calendar_service


async def get_sector_overview(
    session: AsyncSession,
    trade_date: date | None = None,
    sector_type: str = "industry",
) -> SectorOverviewResponse:
    """板块热力图 + 资金净流入/流出 TOP5 + 领涨板块。

    默认取最近交易日（与涨停池同口径）：盘中未收盘时当日板块资金
    尚未写入，返回空（前端提示未收盘），不回退展示前一交易日的旧数据。
    """
    resolved = trade_date or await trade_calendar_service.resolve_latest_trade_date(session)

    stmt = select(SectorFundFlow).where(
        SectorFundFlow.sector_type == sector_type,
        SectorFundFlow.trade_date == resolved,
    )
    rows = list((await session.execute(stmt)).scalars().all())

    def _pct(row: SectorFundFlow) -> float:
        return float(row.change_pct) if row.change_pct is not None else 0.0

    def _inflow(row: SectorFundFlow) -> float:
        return float(row.main_net_inflow) if row.main_net_inflow is not None else 0.0

    by_pct_desc = sorted(rows, key=_pct, reverse=True)
    heat_rows = by_pct_desc[:10] + by_pct_desc[-5:]
    heatmap = [
        SectorHeatItem(
            sector_name=row.sector_name,
            change_pct=float(row.change_pct) if row.change_pct is not None else None,
        )
        for row in heat_rows
    ]

    by_inflow = sorted(rows, key=_inflow, reverse=True)
    top_inflow = [
        SectorFlowItem(
            sector_name=row.sector_name,
            main_net_inflow=_inflow(row),
            top_stock_name=row.top_stock_name,
        )
        for row in by_inflow[:5]
        if _inflow(row) > 0
    ]
    top_outflow = [
        SectorFlowItem(
            sector_name=row.sector_name,
            main_net_inflow=_inflow(row),
            top_stock_name=row.top_stock_name,
        )
        for row in reversed(by_inflow[-5:])
        if _inflow(row) < 0
    ]

    limit_up = await limit_pool_service.get_limit_up(session, resolved)
    industry_limit_count: dict[str, int] = {}
    industry_stocks: dict[str, list[str]] = {}
    for item in limit_up.items:
        if not item.industry:
            continue
        industry_limit_count[item.industry] = (
            industry_limit_count.get(item.industry, 0) + 1
        )
        industry_stocks.setdefault(item.industry, [])
        if item.stock_name and len(industry_stocks[item.industry]) < 2:
            industry_stocks[item.industry].append(item.stock_name)

    leading = [
        LeadingSectorItem(
            sector_name=row.sector_name,
            change_pct=float(row.change_pct) if row.change_pct is not None else None,
            limit_up_count=industry_limit_count.get(row.sector_name, 0),
            main_net_inflow=_inflow(row),
            top_stock_names=(
                industry_stocks.get(row.sector_name)
                or ([row.top_stock_name] if row.top_stock_name else [])
            ),
        )
        for row in by_pct_desc[:5]
    ]

    return SectorOverviewResponse(
        trade_date=resolved,
        heatmap=heatmap,
        top_inflow=top_inflow,
        top_outflow=top_outflow,
        leading=leading,
    )
