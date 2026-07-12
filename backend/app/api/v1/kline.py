"""K-line data API endpoints."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.stock import KlineDataResponse, PaginatedResponse
from app.services import stock_service

router = APIRouter()


@router.get("/{code}", response_model=PaginatedResponse)
async def get_kline(
    code: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """获取股票日 K 线数据。"""
    items, total = await stock_service.get_kline_by_code(
        session, code, start_date, end_date, page, page_size
    )
    if not items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No kline data found",
        )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [KlineDataResponse.model_validate(item) for item in items],
    }
