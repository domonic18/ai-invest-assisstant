"""Base repository providing generic async CRUD operations.

The repository layer is responsible for data access only. It does not manage
transactions; callers (typically services) own the transaction boundary and
perform commit/rollback as needed.
"""

from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """Generic repository for SQLAlchemy models."""

    def __init__(self, session: AsyncSession, model: type[T]) -> None:
        self.session = session
        self.model = model

    async def get(self, obj_id: int) -> T | None:
        """Fetch a single object by primary key."""
        return await self.session.get(self.model, obj_id)

    async def get_all(
        self,
        *,
        order_by: Any | None = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> list[T]:
        """Fetch all objects with optional ordering and pagination."""
        stmt = select(self.model)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        if offset is not None:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self) -> int:
        """Return the total number of objects."""
        from sqlalchemy import func

        stmt = select(func.count()).select_from(self.model)
        return (await self.session.scalar(stmt)) or 0

    def add(self, obj: T) -> None:
        """Add an object to the session."""
        self.session.add(obj)

    async def delete(self, obj: T) -> None:
        """Mark an object for deletion."""
        await self.session.delete(obj)

    async def refresh(self, obj: T) -> None:
        """Refresh an object from the database."""
        await self.session.refresh(obj)

    async def execute(self, stmt: Any) -> Any:
        """Execute a raw SQLAlchemy statement."""
        return await self.session.execute(stmt)

    async def scalar(self, stmt: Any) -> Any:
        """Execute a statement and return a scalar result."""
        return await self.session.scalar(stmt)
