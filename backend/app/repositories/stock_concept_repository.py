"""Repository for stock-concept mapping."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mapping_stock_concept import MappingStockConcept


class StockConceptRepository:
    """Query concept memberships for a given stock code."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_concepts_by_stock(self, code: str) -> list[MappingStockConcept]:
        """Return all concept records for ``code`` ordered by concept name."""
        result = await self.session.execute(
            select(MappingStockConcept)
            .where(MappingStockConcept.stock_code == code)
            .order_by(MappingStockConcept.concept_name)
        )
        return list(result.scalars().all())
