"""Financial health API endpoints."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.financial import FinancialHealthRequest, FinancialHealthResponse
from app.services import financial_service

router = APIRouter()


@router.get("/{code}", response_model=FinancialHealthResponse)
async def get_financial_health(
    code: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    report_date: date | None = None,
) -> FinancialHealthResponse:
    """获取指定股票的财务健康度分析。"""
    params = FinancialHealthRequest(report_date=report_date)
    try:
        return await financial_service.get_health(
            session,
            stock_code=code,
            report_date=params.report_date,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
