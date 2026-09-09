"""板块收盘快照读取服务。"""

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.market import sector_quote_repository
from app.schemas.market import SectorQuoteItem, SectorQuoteResponse


async def get_sector_quotes(
    session: AsyncSession,
    sector_type: str,
    trade_date: date | None = None,
) -> SectorQuoteResponse | None:
    """单日板块行情快照（涨跌幅降序）；未指定日期时取最新快照日。"""
    target = trade_date or await sector_quote_repository.latest_trade_date(
        session, sector_type
    )
    if target is None:
        return None
    rows = await sector_quote_repository.list_sector_quotes(session, sector_type, target)
    return SectorQuoteResponse(
        trade_date=target,
        items=[
            SectorQuoteItem(
                sector_type=row.sector_type,
                sector_code=row.sector_code,
                sector_name=row.sector_name,
                close=float(row.close) if row.close is not None else None,
                change_pct=float(row.change_pct) if row.change_pct is not None else None,
                amount=float(row.amount) if row.amount is not None else None,
                turnover_rate=(
                    float(row.turnover_rate) if row.turnover_rate is not None else None
                ),
                up_count=row.up_count,
                down_count=row.down_count,
                leader_stock_name=row.leader_stock_name,
            )
            for row in rows
        ],
    )
