"""个股资金流向业务服务。"""

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.capital_fund_flow_stock import FundFlow
from app.repositories.market import fund_flow_repository


async def get_fund_flow(
    session: AsyncSession,
    stock_code: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[FundFlow], int]:
    """分页查询资金流向数据。"""
    return await fund_flow_repository.list_paginated(
        session,
        stock_code=stock_code,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )
