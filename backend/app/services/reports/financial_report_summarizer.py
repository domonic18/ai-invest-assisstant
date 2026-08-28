"""Financial report AI summarizer."""

from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnprocessableEntityError
from app.core.locking import redis_lock
from app.models.file_metadata import FileMetadata
from app.services.minio_service import get_minio_service

_SUMMARY_SKILL_ID = "financial-report-summary"
_SUMMARY_TEXT_LIMIT = 12000


class SummaryUnavailableError(UnprocessableEntityError):
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


REPORT_TYPE_LABELS = {
    "annual": "年报",
    "semi_annual": "半年报",
    "q1": "一季报",
    "q3": "三季报",
}


def render_summary_markdown(output: FinancialReportSummaryResult) -> str:
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


class FinancialReportSummarizer:
    """负责财报 PDF 下载、文本抽取与 LLM 摘要生成。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def summarize(self, report: FileMetadata) -> dict[str, Any]:
        """获取财报 AI 摘要：已生成则直返缓存，否则抽 PDF 文本调 LLM 懒生成。

        摘要写回 ``file_metadata.summary`` 全局共享，所有租户复用同一份结果。
        """
        if report.summary:
            return {"summary": report.summary, "cached": True}

        async with redis_lock(
            f"financial-summary:{report.id}", ttl=300, blocking=True, blocking_timeout=120
        ) as acquired:
            if not acquired:
                await self.session.refresh(report)
                if report.summary:
                    return {"summary": report.summary, "cached": True}
                raise SummaryInProgressError(f"财报 {report.id} 摘要正在生成中")

            await self.session.refresh(report)
            if report.summary:
                return {"summary": report.summary, "cached": True}

            file_bytes = await self._load_pdf_bytes(report)
            text = await self._extract_text(file_bytes)
            summary = await self._generate_summary(report, text)

            report.summary = summary
            await self.session.commit()
            return {"summary": summary, "cached": False}

    async def _load_pdf_bytes(self, report: FileMetadata) -> bytes:
        """从 MinIO 下载财报 PDF。"""
        if not report.file_path:
            raise SummaryUnavailableError(f"财报 {report.id} 无可用 PDF 文件")
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
        from app.agent.core.prompt_loader import PromptLoader
        from app.agent.core.prompt_renderer import PromptRenderer
        from app.agent.runtime import run_structured_agent
        from app.core.config import get_settings

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

        output = await run_structured_agent(
            self.session,
            prompt_config=prompt_config,
            user_prompt=user_prompt,
            result_type=FinancialReportSummaryResult,
        )
        return render_summary_markdown(output)
