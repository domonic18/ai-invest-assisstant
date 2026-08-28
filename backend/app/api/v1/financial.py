"""财务健康度 API 路由。"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.financial import (
    FinancialHealthRequest,
    FinancialHealthResponse,
    FinancialHistoryResponse,
)
from app.services.market import financial_service

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


@router.get("/{code}/history", response_model=FinancialHistoryResponse)
async def get_financial_health_history(
    code: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=20)] = 8,
) -> FinancialHistoryResponse:
    """获取指定股票最近多个报告期的财务健康度趋势。"""
    history = await financial_service.get_health_history(
        session,
        stock_code=code,
        limit=limit,
    )
    return FinancialHistoryResponse(stock_code=code, history=history)
