"""Admin stock business services."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import StockBasic
from app.schemas.stock import AdminStockCreate, AdminStockUpdate


class AdminStockService:
    """后台股票管理服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_stocks(
        self, q: str | None = None, page: int = 1, page_size: int = 20
    ) -> tuple[list[StockBasic], int]:
        """分页查询股票列表，支持代码或名称搜索。"""
        stmt = select(StockBasic).order_by(StockBasic.id)
        count_stmt = select(func.count()).select_from(StockBasic)

        if q:
            pattern = f"%{q}%"
            stmt = stmt.where(
                StockBasic.stock_code.ilike(pattern)
                | StockBasic.stock_name.ilike(pattern)
            )
            count_stmt = count_stmt.where(
                StockBasic.stock_code.ilike(pattern)
                | StockBasic.stock_name.ilike(pattern)
            )

        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        total = await self.session.scalar(count_stmt) or 0
        return list(result.scalars().all()), total

    async def create_stock(self, data: AdminStockCreate) -> StockBasic:
        """创建股票基础信息。"""
        stock = StockBasic(
            stock_code=data.stock_code,
            stock_name=data.stock_name,
            market=data.market,
            industry_l1=data.industry_l1,
            industry_l2=data.industry_l2,
            industry_l3=data.industry_l3,
            listing_date=data.listing_date,
        )
        self.session.add(stock)
        await self.session.flush()
        await self.session.refresh(stock)
        return stock

    async def update_stock(
        self, stock_id: int, data: AdminStockUpdate
    ) -> StockBasic | None:
        """更新股票基础信息。"""
        stock = await self.session.get(StockBasic, stock_id)
        if not stock:
            return None

        if data.stock_name is not None:
            stock.stock_name = data.stock_name
        if data.market is not None:
            stock.market = data.market
        if data.industry_l1 is not None:
            stock.industry_l1 = data.industry_l1
        if data.industry_l2 is not None:
            stock.industry_l2 = data.industry_l2
        if data.industry_l3 is not None:
            stock.industry_l3 = data.industry_l3
        if data.listing_date is not None:
            stock.listing_date = data.listing_date

        await self.session.flush()
        await self.session.refresh(stock)
        return stock

    async def delete_stock(self, stock_id: int) -> None:
        """删除股票基础信息。"""
        stock = await self.session.get(StockBasic, stock_id)
        if not stock:
            raise ValueError(f"Stock {stock_id} not found")
        await self.session.delete(stock)
        await self.session.flush()

    def _to_response(self, stock: StockBasic) -> dict[str, Any]:
        """序列化为股票响应字典。"""
        return {
            "id": stock.id,
            "stock_code": stock.stock_code,
            "stock_name": stock.stock_name,
            "market": stock.market,
            "industry_l1": stock.industry_l1,
            "industry_l2": stock.industry_l2,
            "industry_l3": stock.industry_l3,
            "listing_date": stock.listing_date,
            "created_at": stock.created_at,
        }
