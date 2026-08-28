"""Auction data API endpoints."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.stock import (
    AuctionDataResponse,
    IndexAuctionTrendResponse,
    PaginatedResponse,
)
from app.services import auction_service
from app.services import market as stock_service

router = APIRouter()


@router.get("/index-trend", response_model=IndexAuctionTrendResponse)
async def get_index_auction_trend(
    session: Annotated[AsyncSession, Depends(get_db)],
    days: Annotated[int, Query(ge=1, le=250)] = 30,
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
) -> IndexAuctionTrendResponse:
    """指数集合竞价成交额趋势（上证/科创50/创业板，亿元，日期升序）。

    指定 start_date/end_date 时按日期区间查询，否则取最近 days 个交易日。
    """
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_date must not be after end_date",
        )
    return await auction_service.get_index_auction_trend(
        session, days, start_date, end_date
    )


@router.get("/{code}", response_model=PaginatedResponse)
async def get_auction(
    code: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    trade_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """获取股票集合竞价数据。"""
    items, total = await stock_service.get_auction_by_code(
        session, code, trade_date, page, page_size
    )
    if not items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No auction data found",
        )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [AuctionDataResponse.model_validate(item) for item in items],
    }
