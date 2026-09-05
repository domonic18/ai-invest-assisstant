"""个股基础信息仓储。"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import StockBasic
from app.repositories.base import BaseRepository


class StockRepository(BaseRepository[StockBasic]):
    """个股基础信息的数据访问。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, StockBasic)

    async def search(
        self,
        q: str | None = None,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[StockBasic], int]:
        """按代码或名称搜索股票，返回分页结果。"""
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
        """返回给定代码集合的 stock_code 到 stock_name 映射。

        ``stock_basic`` 仅在 ``(stock_code, market)`` 上唯一，同一代码可能
        出现在多个市场，取先遇到的名字。
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

    async def get_codes_by_names(self, names: list[str]) -> dict[str, str]:
        """返回给定名称集合的 stock_name 到 stock_code 映射（同名取先遇到）。"""
        if not names:
            return {}
        stmt = select(StockBasic.stock_name, StockBasic.stock_code).where(
            StockBasic.stock_name.in_(names)
        )
        result = await self.execute(stmt)
        codes: dict[str, str] = {}
        for name, code in result.all():
            codes.setdefault(name, code)
        return codes
