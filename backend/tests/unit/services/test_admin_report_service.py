"""Unit tests for admin report service."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.file_metadata import FileMetadataCreate, FileMetadataUpdate
from app.services.admin.reports import AdminReportService


def _result_mock(items=None, scalar=None):
    result = MagicMock()
    result.scalars.return_value.all.return_value = items or []
    result.scalar_one_or_none.return_value = scalar
    return result


@pytest.mark.unit
class TestAdminReportService:
    @pytest.fixture
    def service(self) -> AdminReportService:
        session = AsyncMock()
        session.add = MagicMock()
        return AdminReportService(session)

    @pytest.mark.asyncio
    async def test_list_reports(self, service: AdminReportService) -> None:
        mock_report = MagicMock()
        mock_report.stock_code = "000001"
        list_result = _result_mock([mock_report])
        names_result = MagicMock()
        names_result.all.return_value = [("000001", "平安银行")]
        service.session.execute.side_effect = [list_result, names_result]
        service.session.scalar.return_value = 1

        items, total = await service.list_reports()

        assert items == [(mock_report, "平安银行")]
        assert total == 1

    @pytest.mark.asyncio
    async def test_list_reports_without_stock_code(self, service: AdminReportService) -> None:
        mock_report = MagicMock()
        mock_report.stock_code = None
        service.session.execute.return_value = _result_mock([mock_report])
        service.session.scalar.return_value = 1

        items, total = await service.list_reports()

        assert items == [(mock_report, None)]
        assert total == 1

    @pytest.mark.asyncio
    async def test_create_report(self, service: AdminReportService) -> None:
        data = FileMetadataCreate(
            file_path="s3://reports/1.pdf",
            file_type="pdf",
            stock_code="000001",
            report_date=date(2024, 1, 1),
        )
        result = await service.create_report(data)

        assert result.file_path == "s3://reports/1.pdf"
        service.session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_report(self, service: AdminReportService) -> None:
        report = MagicMock()
        service.session.get.return_value = report

        result = await service.update_report(
            1, FileMetadataUpdate(broker="Test Broker")
        )

        assert result == report
        assert report.broker == "Test Broker"

    @pytest.mark.asyncio
    async def test_delete_report(self, service: AdminReportService) -> None:
        report = MagicMock()
        service.session.get.return_value = report

        await service.delete_report(1)

        service.session.delete.assert_awaited_once_with(report)
