"""Stock basic information API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.stock import (
    StockBasicResponse,
    StockSearchRequest,
)
from app.services import stock_service

router = APIRouter()


@router.get("/search", response_model=list[StockBasicResponse])
async def search_stocks(
    q: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 20,
) -> list[StockBasicResponse]:
    """根据股票代码或名称搜索。"""
    request = StockSearchRequest(q=q, limit=limit)
    items = await stock_service.search_stocks(session, request.q, request.limit)
    return [StockBasicResponse.model_validate(item) for item in items]


@router.get("/{code}", response_model=StockBasicResponse)
async def get_stock(
    code: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    market: str | None = None,
) -> StockBasicResponse:
    """获取股票基础信息。"""
    item = await stock_service.get_stock_by_code(session, code, market)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stock not found",
        )
    return StockBasicResponse.model_validate(item)
