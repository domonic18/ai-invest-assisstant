"""File metadata repository."""

from sqlalchemy import func, select
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
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[FileMetadata], int]:
        """Return paginated file metadata with optional filters."""
        stmt = select(FileMetadata).order_by(FileMetadata.created_at.desc())
        count_stmt = select(func.count()).select_from(FileMetadata)

        filters = []
        if stock_code:
            filters.append(FileMetadata.stock_code == stock_code)
        if file_type:
            filters.append(FileMetadata.file_type == file_type)

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
