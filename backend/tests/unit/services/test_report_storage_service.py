"""报告存储占用统计服务单元测试。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.report_storage import ReportStorageSummary
from app.services.admin.report_storage_service import ReportStorageService


def _session_with_rows(rows: list[tuple]) -> AsyncMock:
    session = AsyncMock()
    result = MagicMock()
    result.all.return_value = rows
    session.execute = AsyncMock(return_value=result)
    return session


@pytest.mark.unit
async def test_storage_summary_aggregates_by_type() -> None:
    session = _session_with_rows(
        [
            ("research_report", 12, 1024 ** 3),
            ("financial_report", 5, 500 * 1024 ** 2),
            ("announcement", 3, 0),
        ]
    )
    summary = await ReportStorageService(session).get_storage_summary()

    assert isinstance(summary, ReportStorageSummary)
    assert summary.total_file_count == 20
    assert summary.total_size_bytes == 1024 ** 3 + 500 * 1024 ** 2
    research = next(i for i in summary.items if i.file_type == "research_report")
    assert research.file_count == 12
    assert research.size_bytes == 1024 ** 3


@pytest.mark.unit
async def test_storage_summary_empty() -> None:
    session = _session_with_rows([])
    summary = await ReportStorageService(session).get_storage_summary()

    assert summary.items == []
    assert summary.total_file_count == 0
    assert summary.total_size_bytes == 0
