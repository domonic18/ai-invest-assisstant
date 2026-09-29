"""个股概念映射仓储。"""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mapping_stock_concept import MappingStockConcept
from app.models.stock import StockBasic


class StockConceptRepository:
    """查询指定股票代码的概念归属。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, concept_id: int) -> MappingStockConcept | None:
        """按主键查单条映射，缺失时返回 None。"""
        result = await self.session.execute(
            select(MappingStockConcept).where(MappingStockConcept.id == concept_id)
        )
        return result.scalars().first()

    async def list_paged(
        self,
        *,
        q: str | None = None,
        concept: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """分页列出映射（stock_name 左联富化），支持股票代码与概念关键词过滤。

        返回 (行列表, 总数)；行含映射全字段 + stock_name。
        """
        stmt = select(
            MappingStockConcept,
            StockBasic.stock_name,
        ).outerjoin(
            StockBasic, StockBasic.stock_code == MappingStockConcept.stock_code
        )
        count_stmt = select(func.count()).select_from(MappingStockConcept)
        if q:
            stmt = stmt.where(MappingStockConcept.stock_code == q.strip())
            count_stmt = count_stmt.where(MappingStockConcept.stock_code == q.strip())
        if concept:
            like = f"%{concept.strip()}%"
            cond = MappingStockConcept.concept_name.ilike(like) | (
                MappingStockConcept.concept_code.ilike(like)
            )
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)
        total = (await self.session.execute(count_stmt)).scalar() or 0
        rows = (
            await self.session.execute(
                stmt.order_by(MappingStockConcept.stock_code, MappingStockConcept.concept_code)
                .offset(offset)
                .limit(limit)
            )
        ).all()
        items = [
            {
                "id": mapping.id,
                "stock_code": mapping.stock_code,
                "concept_code": mapping.concept_code,
                "concept_name": mapping.concept_name,
                "source": mapping.source,
                "updated_at": mapping.updated_at,
                "stock_name": stock_name,
            }
            for mapping, stock_name in rows
        ]
        return items, int(total)

    async def get_stock_name(self, stock_code: str) -> str | None:
        """查询股票名称，未知代码返回 None。"""
        result = await self.session.execute(
            select(StockBasic.stock_name).where(StockBasic.stock_code == stock_code)
        )
        return result.scalars().first()

    async def get_concepts_by_stock(self, code: str) -> list[MappingStockConcept]:
        """返回 ``code`` 的全部概念记录，按概念名称排序。"""
        result = await self.session.execute(
            select(MappingStockConcept)
            .where(MappingStockConcept.stock_code == code)
            .order_by(MappingStockConcept.concept_name)
        )
        return list(result.scalars().all())

    async def get_concepts_by_stocks(self, codes: list[str]) -> dict[str, list[str]]:
        """批量返回各股票的概念名称列表（按概念名称排序）；无映射的代码不在结果中。"""
        if not codes:
            return {}
        result = await self.session.execute(
            select(MappingStockConcept.stock_code, MappingStockConcept.concept_name)
            .where(MappingStockConcept.stock_code.in_(codes))
            .order_by(MappingStockConcept.stock_code, MappingStockConcept.concept_name)
        )
        mapping: dict[str, list[str]] = {}
        for stock_code, concept_name in result.all():
            mapping.setdefault(stock_code, []).append(concept_name)
        return mapping
