"""研报业务服务。"""

from datetime import date
from typing import Any

import structlog
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.core.prompt_loader import PromptLoader
from app.agent.core.prompt_renderer import PromptRenderer
from app.core.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError, UnprocessableEntityError
from app.core.locking import redis_lock
from app.models.news_announcement import NewsAnnouncement
from app.repositories.reports.news_announcement_repository import NewsAnnouncementRepository
from app.schemas.news_announcement import (
    ResearchReportDetailResponse,
    ResearchReportResponse,
)

logger = structlog.get_logger(__name__)

_SUMMARY_SKILL_ID = "research-report-summary"
_SUMMARY_TEXT_LIMIT = 12000


class SummaryUnavailableError(UnprocessableEntityError):
    """研报 PDF 不可用（无 MinIO 文件且无法从来源下载），无法生成摘要。"""


class SummaryInProgressError(ConflictError):
    """其他请求正在生成该研报的摘要。"""


class ResearchReportSummaryResult(BaseModel):
    """LLM 结构化输出：单篇研报摘要字段（正文缺失时输出空字符串）。"""

    rating: str = ""
    target_price: str = ""
    core_logic: str = ""
    earnings_forecast: str = ""
    risk_warning: str = ""


class ResearchService:
    """研报业务服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = NewsAnnouncementRepository(session)

    async def list_reports(
        self,
        stock_code: str | None = None,
        q: str | None = None,
        broker: str | None = None,
        industry: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[NewsAnnouncement], int]:
        """分页查询研报列表。"""
        offset = (page - 1) * page_size
        return await self.repo.list_paginated(
            doc_type="research",
            stock_code=stock_code,
            q=q,
            broker=broker,
            industry=industry,
            start_date=start_date,
            end_date=end_date,
            order_by=NewsAnnouncement.publish_date.desc().nullslast(),
            offset=offset,
            limit=page_size,
        )

    async def get_report(self, report_id: int) -> NewsAnnouncement | None:
        """按 ID 查询研报详情。"""
        return await self.repo.get(report_id)

    async def list_filters(self) -> dict[str, list[str]]:
        """已采研报的券商/行业去重列表（快筛数据源）。"""
        brokers, industries = await self.repo.list_research_filters()
        return {"brokers": brokers, "industries": industries}

    async def get_pdf_url(self, report_id: int) -> str | None:
        """返回研报 PDF 的预签名下载地址；无已存文件时返回 None。"""
        report = await self.get_report(report_id)
        if report is None:
            raise NotFoundError(f"Research report {report_id} not found")
        file_path = (report.extra or {}).get("file_path")
        if not file_path:
            return None
        from app.services.common.minio_service import get_minio_service

        return await get_minio_service().get_presigned_url(file_path)

    async def summarize_report(self, report_id: int) -> dict[str, Any]:
        """获取研报 AI 摘要：已生成则直返缓存，否则抽 PDF 文本调 LLM 懒生成。

        摘要写回 ``news_announcement.summary`` 全局共享，所有租户复用同一份结果。
        """
        report = await self.get_report(report_id)
        if report is None:
            raise NotFoundError(f"Research report {report_id} not found")

        if report.summary:
            return {"summary": report.summary, "cached": True}

        async with redis_lock(
            f"research-summary:{report_id}", ttl=300, blocking=True, blocking_timeout=120
        ) as acquired:
            if not acquired:
                await self.session.refresh(report)
                if report.summary:
                    return {"summary": report.summary, "cached": True}
                raise SummaryInProgressError(f"研报 {report_id} 摘要正在生成中")

            await self.session.refresh(report)
            if report.summary:
                return {"summary": report.summary, "cached": True}

            file_bytes = await self._load_pdf_bytes(report)
            text = await self._extract_text(file_bytes)
            summary = await self._generate_summary(report, text)

            report.summary = summary
            await self.session.commit()
            logger.info("research_report_summary_generated", report_id=report_id)
            return {"summary": summary, "cached": False}

    async def _load_pdf_bytes(self, report: NewsAnnouncement) -> bytes:
        """定位研报 PDF：优先 MinIO 已存文件，否则从来源 URL 下载并补存。"""
        from app.services.common.minio_service import get_minio_service

        minio = get_minio_service()
        file_path = (report.extra or {}).get("file_path")
        if file_path:
            return await minio.download_file(file_path)

        if not report.source_url:
            raise SummaryUnavailableError(f"研报 {report.id} 无可用 PDF 来源")

        from collector.spiders.eastmoney_research_report import (
            download_research_pdf,
        )

        try:
            file_bytes = await download_research_pdf(report.source_url)
        except Exception as exc:  # noqa: BLE001
            raise SummaryUnavailableError(
                f"研报 {report.id} PDF 下载失败: {exc}"
            ) from exc

        from collector.stores.research_report_store import ResearchReportStore

        item = {
            "stock_code": report.stock_code,
            "title": report.title,
            "publish_date": report.publish_date,
            "source_url": report.source_url,
            "industry_tags": report.industry_tags,
            "extra": dict(report.extra or {}),
            "file_bytes": file_bytes,
            "file_size": len(file_bytes),
        }
        _, errors = await ResearchReportStore(minio=minio).save_many([item])
        if errors:
            raise SummaryUnavailableError(f"研报 {report.id} PDF 补存失败: {errors[0]}")
        await self.session.refresh(report)
        return file_bytes

    async def _extract_text(self, file_bytes: bytes) -> str:
        from app.services.common.knowledge_base_service import get_knowledge_base_service

        text = await get_knowledge_base_service().extract_text(file_bytes, "pdf")
        if not text:
            raise SummaryUnavailableError("PDF 文本抽取失败或内容为空")
        return text[:_SUMMARY_TEXT_LIMIT]

    async def _generate_summary(self, report: NewsAnnouncement, text: str) -> str:
        # 延迟导入：agent 运行时顶层依赖 services，避免 services 聚合时环导入
        from app.agent.runtime.structured import run_structured

        prompt_config = PromptLoader(get_settings().prompts_dir).load(
            "skills", _SUMMARY_SKILL_ID
        )
        extra = report.extra or {}
        user_prompt = PromptRenderer.render(
            prompt_config.user_prompt_template,
            title=report.title,
            stock_name=extra.get("stock_name") or report.stock_code or "未知",
            stock_code=report.stock_code or "未知",
            broker=extra.get("broker") or "未知",
            rating=extra.get("rating") or "未知",
            publish_date=(
                report.publish_date.date().isoformat() if report.publish_date else "未知"
            ),
            report_text=text,
        )

        output = await run_structured(
            self.session,
            result_type=ResearchReportSummaryResult,
            user_prompt=user_prompt,
        )
        return _render_summary_markdown(output)


def _render_summary_markdown(output: ResearchReportSummaryResult) -> str:
    """结构化摘要渲染为统一 Markdown（头部键值 + 小标题分区）。"""
    parts: list[str] = []
    header = []
    if output.rating:
        header.append(f"**投资评级**：{output.rating}")
    if output.target_price:
        header.append(f"**目标价**：{output.target_price}")
    if header:
        parts.append("　".join(header))
    if output.core_logic:
        parts.append(f"### 核心逻辑\n{output.core_logic}")
    if output.earnings_forecast:
        parts.append(f"### 盈利预测\n{output.earnings_forecast}")
    if output.risk_warning:
        parts.append(f"### 风险提示\n{output.risk_warning}")
    return "\n\n".join(parts)


def _derived_fields(report: NewsAnnouncement) -> dict[str, Any]:
    """从 extra/summary 派生列表展示字段。"""
    extra = report.extra or {}
    tags = report.industry_tags or []
    return {
        "broker": extra.get("broker"),
        "rating": extra.get("rating"),
        "pages": extra.get("pages"),
        "industry": tags[0] if tags else None,
        "has_summary": bool(report.summary),
    }


def to_report_response(report: NewsAnnouncement) -> ResearchReportResponse:
    return ResearchReportResponse.model_validate(report).model_copy(
        update=_derived_fields(report)
    )


def to_report_detail_response(report: NewsAnnouncement) -> ResearchReportDetailResponse:
    return ResearchReportDetailResponse.model_validate(report).model_copy(
        update=_derived_fields(report)
    )


# 模块级兼容旧调用点的辅助函数。
async def list_reports(
    session: AsyncSession,
    stock_code: str | None = None,
    q: str | None = None,
    broker: str | None = None,
    industry: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[NewsAnnouncement], int]:
    return await ResearchService(session).list_reports(
        stock_code=stock_code,
        q=q,
        broker=broker,
        industry=industry,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )


async def get_report(session: AsyncSession, report_id: int) -> NewsAnnouncement | None:
    return await ResearchService(session).get_report(report_id)


async def list_filters(session: AsyncSession) -> dict[str, list[str]]:
    return await ResearchService(session).list_filters()


async def get_pdf_url(session: AsyncSession, report_id: int) -> str | None:
    return await ResearchService(session).get_pdf_url(report_id)


async def summarize_report(session: AsyncSession, report_id: int) -> dict[str, Any]:
    return await ResearchService(session).summarize_report(report_id)
