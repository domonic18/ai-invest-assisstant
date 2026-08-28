"""个股概念映射仓储。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mapping_stock_concept import MappingStockConcept


class StockConceptRepository:
    """查询指定股票代码的概念归属。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_concepts_by_stock(self, code: str) -> list[MappingStockConcept]:
        """返回 ``code`` 的全部概念记录，按概念名称排序。"""
        result = await self.session.execute(
            select(MappingStockConcept)
            .where(MappingStockConcept.stock_code == code)
            .order_by(MappingStockConcept.concept_name)
        )
        return list(result.scalars().all())
