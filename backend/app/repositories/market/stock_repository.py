"""Stock repository."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import StockBasic
from app.repositories.base import BaseRepository


class StockRepository(BaseRepository[StockBasic]):
    """Data access for stock basic information."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, StockBasic)

    async def search(
        self,
        q: str | None = None,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[StockBasic], int]:
        """Search stocks by code or name and return paginated results."""
        stmt = select(StockBasic).order_by(StockBasic.id)
        count_stmt = select(func.count()).select_from(StockBasic)

        if q:
            pattern = f"%{q}%"
            filter_clause = (
                StockBasic.stock_code.ilike(pattern)
                | StockBasic.stock_name.ilike(pattern)
            )
            stmt = stmt.where(filter_clause)
            count_stmt = count_stmt.where(filter_clause)

        stmt = stmt.offset(offset).limit(limit)
        result = await self.execute(stmt)
        total = (await self.scalar(count_stmt)) or 0
        return list(result.scalars().all()), total

    async def get_names_by_codes(self, codes: list[str]) -> dict[str, str]:
        """Return a mapping of stock_code to stock_name for the given codes.

        ``stock_basic`` is unique on ``(stock_code, market)`` only, so a code may
        appear in multiple markets; the first name encountered wins.
        """
        if not codes:
            return {}
        stmt = select(StockBasic.stock_code, StockBasic.stock_name).where(
            StockBasic.stock_code.in_(codes)
        )
        result = await self.execute(stmt)
        names: dict[str, str] = {}
        for code, name in result.all():
            names.setdefault(code, name)
        return names
