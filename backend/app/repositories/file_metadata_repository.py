"""File metadata repository."""

from datetime import date, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file_metadata import FileMetadata
from app.repositories.base import BaseRepository


class FileMetadataRepository(BaseRepository[FileMetadata]):
    """Data access for file metadata."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, FileMetadata)

    async def list_paginated(
        self,
        *,
        stock_code: str | None = None,
        file_type: str | None = None,
        q: str | None = None,
        q_stock_codes: list[str] | None = None,
        report_type: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[FileMetadata], int]:
        """Return paginated file metadata with optional filters.

        ``q_stock_codes`` 是与关键词同义匹配到的股票代码集合（名称/代码模糊命中），
        与标题匹配取 OR，使搜索同时覆盖标题、股票名称和代码。
        """
        stmt = select(FileMetadata).order_by(
            FileMetadata.report_date.desc().nullslast(),
            FileMetadata.created_at.desc(),
        )
        count_stmt = select(func.count()).select_from(FileMetadata)

        filters = []
        if stock_code:
            filters.append(FileMetadata.stock_code == stock_code)
        if file_type:
            filters.append(FileMetadata.file_type == file_type)
        if q:
            q_conditions = [FileMetadata.original_name.ilike(f"%{q}%")]
            if q_stock_codes:
                q_conditions.append(FileMetadata.stock_code.in_(q_stock_codes))
            filters.append(or_(*q_conditions))
        if report_type:
            filters.append(FileMetadata.report_type == report_type)
        if start_date:
            filters.append(FileMetadata.report_date >= start_date)
        if end_date:
            filters.append(FileMetadata.report_date < end_date + timedelta(days=1))

        if filters:
            condition = filters[0]
            for f in filters[1:]:
                condition = condition & f
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)

        stmt = stmt.offset(offset).limit(limit)
        result = await self.execute(stmt)
        total = (await self.scalar(count_stmt)) or 0
        return list(result.scalars().all()), total
