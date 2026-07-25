"""Financial report (earnings filings) business services."""

from datetime import date
from typing import Any, cast

import structlog
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.core.llm_router import build_agent
from app.agent.core.prompt_loader import PromptLoader
from app.agent.core.prompt_renderer import PromptRenderer
from app.core.config import get_settings
from app.models.collector_log import CollectorLog
from app.models.file_metadata import FileMetadata
from app.repositories.collector_log_repository import CollectorLogRepository
from app.repositories.file_metadata_repository import FileMetadataRepository
from app.repositories.stock_repository import StockRepository
from app.schemas.file_metadata import FinancialReportResponse
from app.services.llm_config_service import resolve_default_llm
from collector.core.locks import redis_lock
from collector.runtime.dispatcher import dispatch_collector_task

logger = structlog.get_logger(__name__)

_SUMMARY_SKILL_ID = "financial-report-summary"
_SUMMARY_TEXT_LIMIT = 12000
_FILE_TYPE = "financial_report"

REPORT_TYPE_LABELS = {
    "annual": "年报",
    "semi_annual": "半年报",
    "q1": "一季报",
    "q3": "三季报",
}


class SummaryUnavailableError(Exception):
    """财报 PDF 不可用，无法生成摘要。"""


class SummaryInProgressError(Exception):
    """其他请求正在生成该财报的摘要。"""


class FinancialReportSummaryResult(BaseModel):
    """LLM 结构化输出：单篇财报摘要字段（正文缺失时输出空字符串）。"""

    core_performance: str = ""
    revenue_profit: str = ""
    business_highlights: str = ""
    risk_warning: str = ""
    outlook: str = ""


class FinancialReportService:
    """Financial report business services."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = FileMetadataRepository(session)

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
            raise ValueError(f"股票 {stock_code} 不存在")

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
            raise ValueError(f"Financial report {report_id} not found")
        if not report.file_path:
            return None
        from app.services.minio_service import get_minio_service

        return await get_minio_service().get_presigned_url(report.file_path)

    async def summarize_report(self, report_id: int) -> dict[str, Any]:
        """获取财报 AI 摘要：已生成则直返缓存，否则抽 PDF 文本调 LLM 懒生成。

        摘要写回 ``file_metadata.summary`` 全局共享，所有租户复用同一份结果。
        """
        report = await self.get_report(report_id)
        if report is None:
            raise ValueError(f"Financial report {report_id} not found")

        if report.summary:
            return {"summary": report.summary, "cached": True}

        async with redis_lock(
            f"financial-summary:{report_id}", ttl=300, blocking=True, blocking_timeout=120
        ) as acquired:
            if not acquired:
                await self.session.refresh(report)
                if report.summary:
                    return {"summary": report.summary, "cached": True}
                raise SummaryInProgressError(f"财报 {report_id} 摘要正在生成中")

            await self.session.refresh(report)
            if report.summary:
                return {"summary": report.summary, "cached": True}

            file_bytes = await self._load_pdf_bytes(report)
            text = await self._extract_text(file_bytes)
            summary = await self._generate_summary(report, text)

            report.summary = summary
            await self.session.commit()
            logger.info("financial_report_summary_generated", report_id=report_id)
            return {"summary": summary, "cached": False}

    async def _load_pdf_bytes(self, report: FileMetadata) -> bytes:
        """从 MinIO 下载财报 PDF。"""
        if not report.file_path:
            raise SummaryUnavailableError(f"财报 {report.id} 无可用 PDF 文件")
        from app.services.minio_service import get_minio_service

        try:
            return await get_minio_service().download_file(report.file_path)
        except Exception as exc:  # noqa: BLE001
            raise SummaryUnavailableError(
                f"财报 {report.id} PDF 下载失败: {exc}"
            ) from exc

    async def _extract_text(self, file_bytes: bytes) -> str:
        from app.services.knowledge_base_service import get_knowledge_base_service

        text = await get_knowledge_base_service().extract_text(file_bytes, "pdf")
        if not text:
            raise SummaryUnavailableError("PDF 文本抽取失败或内容为空")
        return text[:_SUMMARY_TEXT_LIMIT]

    async def _generate_summary(self, report: FileMetadata, text: str) -> str:
        prompt_config = PromptLoader(get_settings().prompts_dir).load(
            "skills", _SUMMARY_SKILL_ID
        )
        user_prompt = PromptRenderer.render(
            prompt_config.user_prompt_template,
            title=report.original_name or "未知",
            stock_code=report.stock_code or "未知",
            report_type=REPORT_TYPE_LABELS.get(report.report_type or "", "未知"),
            report_date=report.report_date.isoformat() if report.report_date else "未知",
            report_text=text,
        )

        resolved = await resolve_default_llm(self.session)
        model_config = {
            "provider": resolved.provider,
            "model": resolved.model_name,
            "api_key": resolved.api_key,
            "base_url": resolved.base_url,
        }
        agent = build_agent(
            prompt_config=prompt_config,
            model_config=model_config,
            result_type=FinancialReportSummaryResult,
        )
        result = await agent.run(user_prompt)
        return _render_summary_markdown(
            cast(FinancialReportSummaryResult, result.output)
        )


def _render_summary_markdown(output: FinancialReportSummaryResult) -> str:
    """结构化摘要渲染为统一 Markdown（小标题分区）。"""
    parts: list[str] = []
    if output.core_performance:
        parts.append(f"### 核心业绩\n{output.core_performance}")
    if output.revenue_profit:
        parts.append(f"### 营收与利润\n{output.revenue_profit}")
    if output.business_highlights:
        parts.append(f"### 经营亮点\n{output.business_highlights}")
    if output.risk_warning:
        parts.append(f"### 风险提示\n{output.risk_warning}")
    if output.outlook:
        parts.append(f"### 未来展望\n{output.outlook}")
    return "\n\n".join(parts)


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
