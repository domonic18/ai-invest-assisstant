"""Financial report (earnings filings) business services."""

from datetime import date
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.collector_log import CollectorLog
from app.models.file_metadata import FileMetadata
from app.repositories.admin.collector_log_repository import CollectorLogRepository
from app.repositories.market.stock_repository import StockRepository
from app.repositories.reports.file_metadata_repository import FileMetadataRepository
from app.schemas.file_metadata import FinancialReportResponse
from app.services.reports.financial_report_summarizer import FinancialReportSummarizer
from collector.runtime.dispatcher import dispatch_collector_task

logger = structlog.get_logger(__name__)

_FILE_TYPE = "financial_report"


class FinancialReportService:
    """Financial report business services."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = FileMetadataRepository(session)
        self.summarizer = FinancialReportSummarizer(session)

    async def list_reports(
        self,
        stock_code: str | None = None,
        q: str | None = None,
        report_type: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[FileMetadata], int]:
        """分页查询财报列表。

        关键词 ``q`` 除匹配标题外，还会模糊命中股票名称/代码（经 stock_basic
        反查代码集合），保证按公司名（如「奥比中光」）也能搜到对应财报。
        """
        offset = (page - 1) * page_size
        q_stock_codes: list[str] | None = None
        if q:
            stocks, _ = await StockRepository(self.session).search(q, limit=50)
            q_stock_codes = list({s.stock_code for s in stocks})
        return await self.repo.list_paginated(
            file_type=_FILE_TYPE,
            stock_code=stock_code,
            q=q,
            q_stock_codes=q_stock_codes,
            report_type=report_type,
            start_date=start_date,
            end_date=end_date,
            offset=offset,
            limit=page_size,
        )

    async def get_report(self, report_id: int) -> FileMetadata | None:
        """按 ID 查询财报详情（限定 file_type=financial_report）。"""
        report = await self.repo.get(report_id)
        if report is None or report.file_type != _FILE_TYPE:
            return None
        return report

    async def get_stock_names(
        self, reports: list[FileMetadata]
    ) -> dict[str, str]:
        """批量查询财报对应股票代码的名称映射。"""
        codes = [r.stock_code for r in reports if r.stock_code]
        return await StockRepository(self.session).get_names_by_codes(codes)

    async def trigger_collect(
        self,
        stock_code: str,
        report_types: list[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> CollectorLog:
        """为单只股票分发 cninfo 财报采集任务（异步，worker 执行）。

        必须钉死 ``preferred_source="cninfo"``：该 task 的 eastmoney 渠道采的是
        财务三表数据，只有 cninfo 会把财报 PDF 落到 file_metadata。
        """
        stocks, _ = await StockRepository(self.session).search(stock_code, limit=1)
        if not any(s.stock_code == stock_code for s in stocks):
            raise NotFoundError(f"股票 {stock_code} 不存在")

        params: dict[str, Any] = {
            "symbols": [stock_code],
            "preferred_source": "cninfo",
        }
        if report_types:
            params["report_types"] = report_types
        if start_date:
            params["start_date"] = start_date.isoformat()
        if end_date:
            params["end_date"] = end_date.isoformat()
        return await dispatch_collector_task(
            session=self.session, task_name="financial-report", params=params
        )

    async def get_collect_log(self, log_id: int) -> CollectorLog | None:
        """按 ID 查询财报采集日志（限定 task_name=financial-report）。"""
        log = await CollectorLogRepository(self.session).get(log_id)
        if log is None or log.task_name != "financial-report":
            return None
        return log

    async def get_pdf_url(self, report_id: int) -> str | None:
        """返回财报 PDF 的预签名下载地址；无已存文件时返回 None。"""
        report = await self.get_report(report_id)
        if report is None:
            raise NotFoundError(f"Financial report {report_id} not found")
        if not report.file_path:
            return None
        from app.services.common.minio_service import get_minio_service

        return await get_minio_service().get_presigned_url(report.file_path)

    async def summarize_report(self, report_id: int) -> dict[str, Any]:
        """获取财报 AI 摘要。"""
        report = await self.get_report(report_id)
        if report is None:
            raise NotFoundError(f"Financial report {report_id} not found")
        result = await self.summarizer.summarize(report)
        if not result["cached"]:
            logger.info("financial_report_summary_generated", report_id=report_id)
        return result


def to_report_response(
    report: FileMetadata, stock_name: str | None = None
) -> FinancialReportResponse:
    return FinancialReportResponse.model_validate(report).model_copy(
        update={
            "title": report.original_name,
            "stock_name": stock_name,
            "has_summary": bool(report.summary),
        }
    )


# Module-level helpers for backwards compatibility.
async def list_reports(
    session: AsyncSession,
    stock_code: str | None = None,
    q: str | None = None,
    report_type: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[FileMetadata], int]:
    return await FinancialReportService(session).list_reports(
        stock_code=stock_code,
        q=q,
        report_type=report_type,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )


async def get_report(session: AsyncSession, report_id: int) -> FileMetadata | None:
    return await FinancialReportService(session).get_report(report_id)


async def get_pdf_url(session: AsyncSession, report_id: int) -> str | None:
    return await FinancialReportService(session).get_pdf_url(report_id)


async def summarize_report(session: AsyncSession, report_id: int) -> dict[str, Any]:
    return await FinancialReportService(session).summarize_report(report_id)


async def get_stock_names(
    session: AsyncSession, reports: list[FileMetadata]
) -> dict[str, str]:
    return await FinancialReportService(session).get_stock_names(reports)


async def trigger_collect(
    session: AsyncSession,
    stock_code: str,
    report_types: list[str] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> CollectorLog:
    return await FinancialReportService(session).trigger_collect(
        stock_code=stock_code,
        report_types=report_types,
        start_date=start_date,
        end_date=end_date,
    )


async def get_collect_log(session: AsyncSession, log_id: int) -> CollectorLog | None:
    return await FinancialReportService(session).get_collect_log(log_id)
