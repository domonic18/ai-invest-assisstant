"""Fund flow data API endpoints."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.stock import FundFlowResponse, PaginatedResponse
from app.services import stock_service

router = APIRouter()


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
