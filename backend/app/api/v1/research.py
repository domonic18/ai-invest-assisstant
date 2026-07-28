"""Research report API endpoints."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.news_announcement import (
    ResearchReportDetailResponse,
    ResearchReportFiltersResponse,
    ResearchReportListRequest,
)
from app.schemas.stock import PaginatedResponse
from app.services import research_service

router = APIRouter()


@router.get("/", response_model=PaginatedResponse)
async def list_research(
    session: Annotated[AsyncSession, Depends(get_db)],
    stock_code: str | None = None,
    q: str | None = None,
    broker: str | None = None,
    industry: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> PaginatedResponse:
    """查询研报列表，支持股票代码、关键词、券商、行业和发布日期范围筛选。"""
    params = ResearchReportListRequest(
        stock_code=stock_code,
        q=q,
        broker=broker,
        industry=industry,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )
    items, total = await research_service.list_reports(
        session,
        stock_code=params.stock_code,
        q=params.q,
        broker=params.broker,
        industry=params.industry,
        start_date=params.start_date,
        end_date=params.end_date,
        page=params.page,
        page_size=params.page_size,
    )
    return PaginatedResponse(
        total=total,
        page=params.page,
        page_size=params.page_size,
        items=[research_service.to_report_response(item) for item in items],
    )


@router.get("/filters", response_model=ResearchReportFiltersResponse)
async def list_research_filters(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResearchReportFiltersResponse:
    """已采研报的券商/行业去重列表（快筛 badge 数据源）。"""
    filters = await research_service.list_filters(session)
    return ResearchReportFiltersResponse(**filters)


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
    return research_service.to_report_detail_response(report)


@router.get("/{report_id}/pdf-url")
async def get_research_pdf_url(
    report_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """返回研报 PDF 的预签名下载地址；无已存文件时 404。"""
    try:
        url = await research_service.get_pdf_url(session, report_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    if url is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research report PDF not available",
        )
    return {"url": url}


@router.post("/{report_id}/summarize")
async def summarize_research(
    report_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """生成或返回研报 AI 摘要（懒生成，结果全局共享）。

    业务异常（NotFoundError/SummaryUnavailableError/SummaryInProgressError）由全局
    AppError handler 统一转换为 JSONResponse ``{detail: message}``。
    """
    return await research_service.summarize_report(session, report_id)
