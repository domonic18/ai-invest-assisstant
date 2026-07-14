"""Admin report (file metadata) business services."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file_metadata import FileMetadata
from app.schemas.file_metadata import FileMetadataCreate, FileMetadataUpdate


class AdminReportService:
    """后台研报文件管理服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_reports(
        self,
        stock_code: str | None = None,
        file_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[FileMetadata], int]:
        """分页查询研报文件列表。"""
        stmt = select(FileMetadata).order_by(FileMetadata.uploaded_at.desc())
        count_stmt = select(func.count()).select_from(FileMetadata)

        if stock_code:
            stmt = stmt.where(FileMetadata.stock_code == stock_code)
            count_stmt = count_stmt.where(FileMetadata.stock_code == stock_code)
        if file_type:
            stmt = stmt.where(FileMetadata.file_type == file_type)
            count_stmt = count_stmt.where(FileMetadata.file_type == file_type)

        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        total = await self.session.scalar(count_stmt) or 0
        return list(result.scalars().all()), total

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
        self.session.add(report)
        await self.session.flush()
        await self.session.refresh(report)
        return report

    async def update_report(
        self, report_id: int, data: FileMetadataUpdate
    ) -> FileMetadata | None:
        """更新研报文件元数据。"""
        report = await self.session.get(FileMetadata, report_id)
        if not report:
            return None

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(report, field, value)

        report.uploaded_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(report)
        return report

    async def delete_report(self, report_id: int) -> None:
        """删除研报文件元数据。"""
        report = await self.session.get(FileMetadata, report_id)
        if not report:
            raise ValueError(f"Report {report_id} not found")
        await self.session.delete(report)
        await self.session.flush()

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
            "uploaded_at": report.uploaded_at,
        }
