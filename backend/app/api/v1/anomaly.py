"""异动分析 API 路由（板块 / 个股异动榜）。"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.anomaly import SectorAnomalyResponse, StockAnomalyResponse
from app.services.market import sector_anomaly_service, stock_anomaly_service

router = APIRouter()


@router.get("/sector", response_model=SectorAnomalyResponse | None)
async def get_sector_anomaly_board(
    session: Annotated[AsyncSession, Depends(get_db)],
    trade_date: date | None = None,
    sector_type: Annotated[str | None, Query(pattern="^(industry|concept)$")] = None,
) -> SectorAnomalyResponse | None:
    """板块异动榜（强度降序），默认取最新检测日。"""
    return await sector_anomaly_service.get_sector_anomaly_board(
        session, trade_date, sector_type
    )


@router.get("/stock", response_model=StockAnomalyResponse | None)
async def get_stock_anomaly_board(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    trade_date: date | None = None,
) -> StockAnomalyResponse | None:
    """个股异动榜（强度降序，命中自选股带标注），默认取最新检测日。"""
    return await stock_anomaly_service.get_stock_anomaly_board(
        session, trade_date, current_user.id
    )
