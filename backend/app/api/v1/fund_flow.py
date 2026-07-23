"""Fund flow data API endpoints."""

from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.capital_fund_flow_sector import SectorFlowTrendResponse
from app.schemas.stock import FundFlowResponse, PaginatedResponse
from app.services import sector_fund_flow_service, stock_service

router = APIRouter()


@router.get("/sector-trend", response_model=SectorFlowTrendResponse)
async def get_sector_flow_trend(
    session: Annotated[AsyncSession, Depends(get_db)],
    sector_type: Literal["industry", "concept"] = "industry",
    days: Annotated[int, Query(ge=1, le=250)] = 60,
) -> SectorFlowTrendResponse:
    """板块主力净流入趋势（亿元，日期升序，供河流图/排名图使用）。"""
    return await sector_fund_flow_service.get_sector_flow_trend(
        session, sector_type, days
    )


@router.get("/", response_model=PaginatedResponse)
async def get_fund_flow(
    session: Annotated[AsyncSession, Depends(get_db)],
    stock_code: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """获取资金流向数据。"""
    items, total = await stock_service.get_fund_flow(
        session, stock_code, start_date, end_date, page, page_size
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [FundFlowResponse.model_validate(item) for item in items],
    }
