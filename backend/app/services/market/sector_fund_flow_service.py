"""板块资金流向服务：按交易日的板块主力净流入趋势。"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.market import sector_fund_flow_repository
from app.schemas.capital_fund_flow_sector import SectorFlowSeries, SectorFlowTrendResponse
from app.schemas.workbench import SectorFlowItem


async def get_latest_sector_flow(
    session: AsyncSession, sector_type: str = "industry", limit: int = 8
) -> list[SectorFlowItem]:
    """最新一个有数据交易日的板块主力净流入排行（单位换算为亿元）。"""
    rows = await sector_fund_flow_repository.list_latest_day(
        session, sector_type=sector_type, limit=limit
    )
    return [
        SectorFlowItem(
            sector_name=row.sector_name,
            change_pct=round(float(row.change_pct), 2) if row.change_pct is not None else None,
            main_net_inflow=(
                round(float(row.main_net_inflow) / 1e8, 2)
                if row.main_net_inflow is not None
                else None
            ),
            top_stock_name=row.top_stock_name,
        )
        for row in rows
    ]


async def get_sector_flow_trend(
    session: AsyncSession, sector_type: str = "industry", days: int = 60
) -> SectorFlowTrendResponse:
    """最近 N 个交易日指定类型板块的主力净流入趋势（单位换算为亿元）。

    sectors 按区间内累计净流入绝对值降序输出，values 与 dates 对齐，
    某日无数据的板块填 None。
    """
    rows = await sector_fund_flow_repository.list_recent(session, sector_type, days)
    dates = sorted({row.trade_date for row in rows})
    names: dict[str, str] = {}
    amounts: dict[tuple[object, str], float] = {}
    totals: dict[str, float] = {}
    for row in rows:
        names[row.sector_code] = row.sector_name
        if row.main_net_inflow is None:
            continue
        value = round(float(row.main_net_inflow) / 1e8, 2)
        amounts[(row.trade_date, row.sector_code)] = value
        totals[row.sector_code] = totals.get(row.sector_code, 0.0) + abs(value)
    codes = sorted(totals, key=lambda c: totals[c], reverse=True)
    sectors = [
        SectorFlowSeries(
            code=code,
            name=names[code],
            values=[amounts.get((day, code)) for day in dates],
        )
        for code in codes
    ]
    return SectorFlowTrendResponse(dates=dates, sectors=sectors)
