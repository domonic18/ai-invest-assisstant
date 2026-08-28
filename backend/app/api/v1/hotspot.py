"""热点（板块资金流向）API 路由。"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.capital_fund_flow_sector import HotspotListRequest, SectorFundFlowResponse
from app.schemas.stock import PaginatedResponse
from app.services.market import hotspot_service

router = APIRouter()


@router.get("/", response_model=PaginatedResponse)
async def get_hotspots(
    session: Annotated[AsyncSession, Depends(get_db)],
    sector_type: str | None = None,
    trade_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> PaginatedResponse:
    """查询板块资金流向热点，默认按主力净流入排序。"""
    params = HotspotListRequest(
        sector_type=sector_type,
        trade_date=trade_date,
        page=page,
        page_size=page_size,
    )
    items, total = await hotspot_service.list_sectors(
        session,
        sector_type=params.sector_type,
        trade_date=params.trade_date,
        page=params.page,
        page_size=params.page_size,
    )
    return PaginatedResponse(
        total=total,
        page=params.page,
        page_size=params.page_size,
        items=[SectorFundFlowResponse.model_validate(item) for item in items],
    )
