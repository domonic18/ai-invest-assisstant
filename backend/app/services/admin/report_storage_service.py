"""报告文件存储占用统计服务。"""

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file_metadata import FileMetadata
from app.schemas.report_storage import ReportStorageSummary, ReportStorageTypeSummary


class ReportStorageService:
    """聚合 file_metadata.file_size，输出各类型与总计的存储占用。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_storage_summary(self) -> ReportStorageSummary:
        """按 file_type 聚合文件数与字节总量（NULL file_size 不计入）。"""
        rows = (
            await self.session.execute(
                sa.select(
                    FileMetadata.file_type,
                    sa.func.count(),
                    sa.func.coalesce(sa.func.sum(FileMetadata.file_size), 0),
                ).group_by(FileMetadata.file_type)
            )
        ).all()

        items = [
            ReportStorageTypeSummary(
                file_type=file_type,
                file_count=count,
                size_bytes=int(total_size),
            )
            for file_type, count, total_size in rows
        ]
        return ReportStorageSummary(
            items=items,
            total_size_bytes=sum(item.size_bytes for item in items),
            total_file_count=sum(item.file_count for item in items),
        )
