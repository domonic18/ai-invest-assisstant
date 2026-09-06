"""热点（板块资金流向）API 路由。"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.pagination import (
    DEFAULT_PAGE,
    DEFAULT_PAGE_SIZE,
    MAX_SECTOR_PAGE_SIZE,
)
from app.dependencies import get_db
from app.schemas.capital_fund_flow_sector import SectorFundFlowResponse
from app.schemas.stock import PaginatedResponse
from app.services.market import hotspot_service

router = APIRouter()


@router.get("/", response_model=PaginatedResponse)
async def get_hotspots(
    session: Annotated[AsyncSession, Depends(get_db)],
    sector_type: Annotated[str | None, Query(max_length=20)] = None,
    trade_date: Annotated[date | None, Query()] = None,
    page: int = Query(DEFAULT_PAGE, ge=DEFAULT_PAGE),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_SECTOR_PAGE_SIZE),
) -> PaginatedResponse:
    """查询板块资金流向热点，默认按主力净流入排序。"""
    items, total = await hotspot_service.list_sectors(
        session,
        sector_type=sector_type,
        trade_date=trade_date,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[SectorFundFlowResponse.model_validate(item) for item in items],
    )
