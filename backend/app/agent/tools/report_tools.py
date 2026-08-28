"""财报相关助手工具。"""

from datetime import date
from typing import Any

from langchain_core.tools import tool

from app.core.database import AsyncSessionLocal

FINANCIAL_REPORT_MAX_LIMIT = 100


@tool
async def query_financial_reports(
    stock_code: str,
    report_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """查询系统中已存在的财报列表。

    Args:
        stock_code: 6 位股票代码，如 "000001"。
        report_type: 财报类型过滤，可选 annual / semi_annual / q1 / q3。
        start_date: 报告期起始，ISO 格式如 "2024-01-01"。
        end_date: 报告期截止，ISO 格式如 "2024-12-31"。
    """
    from app.services.financial_report_service import FinancialReportService

    try:
        resolved_start = date.fromisoformat(start_date) if start_date else None
        resolved_end = date.fromisoformat(end_date) if end_date else None
    except ValueError:
        return {"error": "start_date / end_date 须为 YYYY-MM-DD 格式"}

    async with AsyncSessionLocal() as session:
        service = FinancialReportService(session)
        items, total = await service.list_reports(
            stock_code=stock_code,
            report_type=report_type,
            start_date=resolved_start,
            end_date=resolved_end,
            page_size=FINANCIAL_REPORT_MAX_LIMIT,
        )
        return {
            "total": total,
            "reports": [
                {
                    "id": item.id,
                    "stock_code": item.stock_code,
                    "report_type": item.report_type,
                    "report_date": item.report_date.isoformat() if item.report_date else None,
                    "original_name": item.original_name,
                    "has_pdf": bool(item.file_path),
                    "has_summary": bool(item.summary),
                    "created_at": item.created_at.isoformat() if item.created_at else None,
                }
                for item in items
            ],
        }


@tool
async def download_financial_reports(
    stock_code: str,
    report_types: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """触发指定股票的财报采集任务（异步）。当系统中缺少所需财报时调用。

    Args:
        stock_code: 6 位股票代码，如 "000001"。
        report_types: 财报类型列表，可选 annual / semi_annual / q1 / q3；缺省则采集全部。
        start_date: 报告期起始，ISO 格式如 "2024-01-01"。
        end_date: 报告期截止，ISO 格式如 "2024-12-31"。
    """
    from app.services.financial_report_service import FinancialReportService

    try:
        resolved_start = date.fromisoformat(start_date) if start_date else None
        resolved_end = date.fromisoformat(end_date) if end_date else None
    except ValueError:
        return {"error": "start_date / end_date 须为 YYYY-MM-DD 格式"}

    async with AsyncSessionLocal() as session:
        service = FinancialReportService(session)
        try:
            log = await service.trigger_collect(
                stock_code,
                report_types=report_types,
                start_date=resolved_start,
                end_date=resolved_end,
            )
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}
        return {"log_id": log.id, "status": log.status}


@tool
async def summarize_financial_report(report_id: int) -> dict[str, Any]:
    """获取单篇财报的 AI 摘要，用于从财报正文中提取业务亮点、风险与前景等定性信息。

    Args:
        report_id: 财报在系统中的 ID（由 query_financial_reports 返回的 id 字段）。
    """
    from app.services.financial_report_service import FinancialReportService

    async with AsyncSessionLocal() as session:
        service = FinancialReportService(session)
        try:
            return await service.summarize_report(report_id)
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}
