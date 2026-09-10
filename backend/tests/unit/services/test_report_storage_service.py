"""报告存储占用统计与清理服务单元测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import InternalError
from app.schemas.report_storage import ReportStorageSummary
from app.services.admin.report_storage_service import ReportStorageService
from app.services.admin.reports import AdminReportService


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


def _cleanup_service(rows: list[SimpleNamespace]) -> object:
    service = AdminReportService.__new__(AdminReportService)
    service.session = AsyncMock()
    service.session.commit = AsyncMock()
    service.session.delete = AsyncMock()
    service.repo = AsyncMock()
    service.repo.list_older_than = AsyncMock(return_value=rows)
    return service


def _stale(path: str, size: int | None) -> SimpleNamespace:
    return SimpleNamespace(file_path=path, file_size=size)


@pytest.mark.unit
async def test_cleanup_removes_objects_and_rows() -> None:
    rows = [_stale("reports/old1.pdf", 100), _stale("reports/old2.pdf", None)]
    service = _cleanup_service(rows)

    with patch(
        "app.services.admin.reports.get_minio_service"
    ) as minio_cls:
        minio_cls.return_value.remove_files = AsyncMock(return_value=[])
        removed, size = await service.cleanup_old_reports(days=90)

    assert (removed, size) == (2, 100)
    assert service.repo.delete.await_count == 2
    service.session.commit.assert_awaited_once()


@pytest.mark.unit
async def test_cleanup_noop_when_nothing_old() -> None:
    service = _cleanup_service([])
    with patch(
        "app.services.admin.reports.get_minio_service"
    ) as minio_cls:
        minio_cls.return_value.remove_files = AsyncMock()
        removed, size = await service.cleanup_old_reports()

    assert (removed, size) == (0, 0)
    minio_cls.return_value.remove_files.assert_not_awaited()
    service.session.commit.assert_not_awaited()


@pytest.mark.unit
async def test_cleanup_partial_failure_keeps_failed_rows() -> None:
    rows = [_stale("reports/a.pdf", 10), _stale("reports/b.pdf", 20)]
    service = _cleanup_service(rows)
    with patch(
        "app.services.admin.reports.get_minio_service"
    ) as minio_cls:
        minio_cls.return_value.remove_files = AsyncMock(
            return_value=["reports/b.pdf"]
        )
        removed, size = await service.cleanup_old_reports()

    assert (removed, size) == (1, 10)
    assert service.repo.delete.await_count == 1


@pytest.mark.unit
async def test_cleanup_minio_error_raises_and_keeps_rows() -> None:
    service = _cleanup_service([_stale("reports/a.pdf", 10)])
    with patch(
        "app.services.admin.reports.get_minio_service"
    ) as minio_cls:
        minio_cls.return_value.remove_files = AsyncMock(
            side_effect=RuntimeError("S3 down")
        )
        with pytest.raises(InternalError):
            await service.cleanup_old_reports()

    service.repo.delete.assert_not_awaited()
    service.session.commit.assert_not_awaited()
