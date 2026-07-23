"""Admin report (file metadata) business services."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file_metadata import FileMetadata
from app.repositories.file_metadata_repository import FileMetadataRepository
from app.repositories.stock_repository import StockRepository
from app.schemas.file_metadata import FileMetadataCreate, FileMetadataUpdate


class AdminReportService:
    """后台研报文件管理服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = FileMetadataRepository(session)
        self.stock_repo = StockRepository(session)

    async def list_reports(
        self,
        stock_code: str | None = None,
        file_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[tuple[FileMetadata, str | None]], int]:
        """分页查询研报文件列表，每条附带股票名称（查不到为 None）。"""
        offset = (page - 1) * page_size
        items, total = await self.repo.list_paginated(
            stock_code=stock_code,
            file_type=file_type,
            offset=offset,
            limit=page_size,
        )
        codes = list({item.stock_code for item in items if item.stock_code})
        names = await self.stock_repo.get_names_by_codes(codes)
        return [
            (item, names.get(item.stock_code) if item.stock_code else None)
            for item in items
        ], total

    async def get_report(self, report_id: int) -> FileMetadata | None:
        """按 ID 查询研报文件元数据。"""
        return await self.repo.get(report_id)

    async def create_report(self, data: FileMetadataCreate) -> FileMetadata:
        """创建研报文件元数据。"""
        report = FileMetadata(
            file_path=data.file_path,
            original_name=data.original_name,
            file_type=data.file_type,
            stock_code=data.stock_code,
            report_date=data.report_date,
            report_type=data.report_type,
            broker=data.broker,
            file_size=data.file_size,
            md5_hash=data.md5_hash,
            download_url=data.download_url,
        )
        self.repo.add(report)
        await self.session.commit()
        await self.repo.refresh(report)
        return report

    async def update_report(
        self, report_id: int, data: FileMetadataUpdate
    ) -> FileMetadata | None:
        """更新研报文件元数据。"""
        report = await self.repo.get(report_id)
        if not report:
            return None

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(report, field, value)

        report.created_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.repo.refresh(report)
        return report

    async def delete_report(self, report_id: int) -> None:
        """删除研报文件元数据。"""
        report = await self.repo.get(report_id)
        if not report:
            raise ValueError(f"Report {report_id} not found")
        await self.repo.delete(report)
        await self.session.commit()

    def _to_response(self, report: FileMetadata) -> dict[str, Any]:
        """序列化为研报响应字典。"""
        return {
            "id": report.id,
            "file_path": report.file_path,
            "original_name": report.original_name,
            "file_type": report.file_type,
            "stock_code": report.stock_code,
            "report_date": report.report_date,
            "report_type": report.report_type,
            "broker": report.broker,
            "file_size": report.file_size,
            "md5_hash": report.md5_hash,
            "download_url": report.download_url,
            "download_count": report.download_count,
            "created_at": report.created_at,
        }
