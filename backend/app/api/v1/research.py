"""Research report API endpoints."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.news_announcement import (
    ResearchReportDetailResponse,
    ResearchReportListRequest,
    ResearchReportResponse,
)
from app.schemas.stock import PaginatedResponse
from app.services import research_service

router = APIRouter()


@router.get("/", response_model=PaginatedResponse)
async def list_research(
    session: Annotated[AsyncSession, Depends(get_db)],
    stock_code: str | None = None,
    q: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> PaginatedResponse:
    """查询研报列表，支持股票代码、关键词和发布日期范围筛选。"""
    params = ResearchReportListRequest(
        stock_code=stock_code,
        q=q,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )
    items, total = await research_service.list_reports(
        session,
        stock_code=params.stock_code,
        q=params.q,
        start_date=params.start_date,
        end_date=params.end_date,
        page=params.page,
        page_size=params.page_size,
    )
    return PaginatedResponse(
        total=total,
        page=params.page,
        page_size=params.page_size,
        items=[ResearchReportResponse.model_validate(item) for item in items],
    )


@router.get("/{report_id}", response_model=ResearchReportDetailResponse)
async def get_research(
    report_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResearchReportDetailResponse:
    """获取单篇研报详情。"""
    report = await research_service.get_report(session, report_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research report not found",
        )
    return ResearchReportDetailResponse.model_validate(report)


@router.post("/{report_id}/summarize")
async def summarize_research(
    report_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """生成或返回研报摘要。"""
    try:
        return await research_service.summarize_report(session, report_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
