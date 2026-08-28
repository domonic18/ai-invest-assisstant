"""Admin stock business services."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import StockBasic
from app.repositories.market.stock_repository import StockRepository
from app.schemas.stock import AdminStockCreate, AdminStockUpdate


class AdminStockService:
    """后台股票管理服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = StockRepository(session)

    async def list_stocks(
        self, q: str | None = None, page: int = 1, page_size: int = 20
    ) -> tuple[list[StockBasic], int]:
        """分页查询股票列表，支持代码或名称搜索。"""
        offset = (page - 1) * page_size
        return await self.repo.search(q=q, offset=offset, limit=page_size)

    async def get_stock(self, stock_id: int) -> StockBasic | None:
        """按 ID 查询股票基础信息。"""
        return await self.repo.get(stock_id)

    async def create_stock(self, data: AdminStockCreate) -> StockBasic:
        """创建股票基础信息。"""
        stock = StockBasic(
            stock_code=data.stock_code,
            stock_name=data.stock_name,
            market=data.market,
            industry_level_1=data.industry_level_1,
            industry_level_2=data.industry_level_2,
            industry_level_3=data.industry_level_3,
            listing_date=data.listing_date,
        )
        self.repo.add(stock)
        await self.session.commit()
        await self.repo.refresh(stock)
        return stock

    async def update_stock(
        self, stock_id: int, data: AdminStockUpdate
    ) -> StockBasic | None:
        """更新股票基础信息。"""
        stock = await self.repo.get(stock_id)
        if not stock:
            return None

        if data.stock_name is not None:
            stock.stock_name = data.stock_name
        if data.market is not None:
            stock.market = data.market
        if data.industry_level_1 is not None:
            stock.industry_level_1 = data.industry_level_1
        if data.industry_level_2 is not None:
            stock.industry_level_2 = data.industry_level_2
        if data.industry_level_3 is not None:
            stock.industry_level_3 = data.industry_level_3
        if data.listing_date is not None:
            stock.listing_date = data.listing_date

        await self.session.commit()
        await self.repo.refresh(stock)
        return stock

    async def delete_stock(self, stock_id: int) -> None:
        """删除股票基础信息。"""
        stock = await self.repo.get(stock_id)
        if not stock:
            raise ValueError(f"Stock {stock_id} not found")
        await self.repo.delete(stock)
        await self.session.commit()

    def _to_response(self, stock: StockBasic) -> dict[str, Any]:
        """序列化为股票响应字典。"""
        return {
            "id": stock.id,
            "stock_code": stock.stock_code,
            "stock_name": stock.stock_name,
            "market": stock.market,
            "industry_level_1": stock.industry_level_1,
            "industry_level_2": stock.industry_level_2,
            "industry_level_3": stock.industry_level_3,
            "listing_date": stock.listing_date,
            "created_at": stock.created_at,
        }
