"""管理后台交易日历 API 端点。"""

from datetime import date
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin_user, get_db
from app.schemas.trade_calendar import (
    TradeCalendarDayResponse,
    TradeCalendarDayUpdate,
    TradeCalendarSeedRequest,
    TradeCalendarSeedResponse,
    TradeCalendarYearResponse,
)
from app.services.admin import trade_calendar_admin

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/trade-calendar",
    dependencies=[Depends(get_current_admin_user)],
)


@router.get("", response_model=TradeCalendarYearResponse)
async def get_trade_calendar_year(
    session: Annotated[AsyncSession, Depends(get_db)],
    year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
) -> TradeCalendarYearResponse:
    """查询年度交易日历与覆盖元信息（月历视图数据源）。"""
    return await trade_calendar_admin.get_year(session, year)


@router.put("/{day}", response_model=TradeCalendarDayResponse)
async def update_trade_calendar_day(
    day: date,
    data: TradeCalendarDayUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TradeCalendarDayResponse:
    """单日人工覆盖（限今天及未来，防历史口径篡改）。"""
    return await trade_calendar_admin.set_day(
        session, day, data.is_trading, data.remark
    )


@router.post("/seed", response_model=TradeCalendarSeedResponse)
async def seed_trade_calendar(
    data: TradeCalendarSeedRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TradeCalendarSeedResponse:
    """新浪日历种子刷新（人工覆盖行不回改）。"""
    years, written = await trade_calendar_admin.seed(session, data.years)
    logger.info(
        "admin_trade_calendar_seeded", years=years, written=written
    )
    return TradeCalendarSeedResponse(years=years, written=written)
