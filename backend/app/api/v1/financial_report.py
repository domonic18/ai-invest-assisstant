"""Financial report (earnings filings) API endpoints."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.file_metadata import (
    FinancialReportCollectLogResponse,
    FinancialReportCollectRequest,
    FinancialReportCollectResponse,
    FinancialReportListRequest,
    FinancialReportResponse,
)
from app.schemas.stock import PaginatedResponse
from app.services import financial_report_service
from app.services.financial_report_service import (
    SummaryInProgressError,
    SummaryUnavailableError,
)

router = APIRouter()


@router.get("/", response_model=PaginatedResponse)
async def list_financial_reports(
    session: Annotated[AsyncSession, Depends(get_db)],
    stock_code: str | None = None,
    q: str | None = None,
    report_type: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> PaginatedResponse:
    """查询财报列表，支持股票代码、关键词、报告类型和报告期范围筛选。"""
    params = FinancialReportListRequest(
        stock_code=stock_code,
        q=q,
        report_type=report_type,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )
    items, total = await financial_report_service.list_reports(
        session,
        stock_code=params.stock_code,
        q=params.q,
        report_type=params.report_type,
        start_date=params.start_date,
        end_date=params.end_date,
        page=params.page,
        page_size=params.page_size,
    )
    names = await financial_report_service.get_stock_names(session, items)
    return PaginatedResponse(
        total=total,
        page=params.page,
        page_size=params.page_size,
        items=[
            financial_report_service.to_report_response(
                item, names.get(item.stock_code or "")
            )
            for item in items
        ],
    )


@router.post("/collect", response_model=FinancialReportCollectResponse)
async def collect_financial_report(
    body: FinancialReportCollectRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> FinancialReportCollectResponse:
    """触发单只股票的财报采集（异步执行，用 collect-logs 轮询进度）。"""
    try:
        log = await financial_report_service.trigger_collect(
            session,
            stock_code=body.stock_code,
            report_types=body.report_types,
            start_date=body.start_date,
            end_date=body.end_date,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return FinancialReportCollectResponse(log_id=log.id, status=log.status)


@router.get(
    "/collect-logs/{log_id}", response_model=FinancialReportCollectLogResponse
)
async def get_collect_log(
    log_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> FinancialReportCollectLogResponse:
    """查询财报采集任务进度。"""
    log = await financial_report_service.get_collect_log(session, log_id)
    if log is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collect log not found",
        )
    return FinancialReportCollectLogResponse(
        log_id=log.id,
        status=log.status,
        records_count=log.records_count,
        error_msg=log.error_msg,
        finished_at=log.finished_at,
    )


@router.get("/{report_id}", response_model=FinancialReportResponse)
async def get_financial_report(
    report_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> FinancialReportResponse:
    """获取单篇财报详情。"""
    report = await financial_report_service.get_report(session, report_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Financial report not found",
        )
    names = await financial_report_service.get_stock_names(session, [report])
    return financial_report_service.to_report_response(
        report, names.get(report.stock_code or "")
    )


@router.get("/{report_id}/pdf-url")
async def get_financial_report_pdf_url(
    report_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """返回财报 PDF 的预签名下载地址；无已存文件时 404。"""
    try:
        url = await financial_report_service.get_pdf_url(session, report_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    if url is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Financial report PDF not available",
        )
    return {"url": url}


@router.post("/{report_id}/summarize")
async def summarize_financial_report(
    report_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """生成或返回财报 AI 摘要（懒生成，结果全局共享）。"""
    try:
        return await financial_report_service.summarize_report(session, report_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except SummaryUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except SummaryInProgressError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
