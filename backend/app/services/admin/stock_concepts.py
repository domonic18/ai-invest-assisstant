"""后台题材（股票-概念）映射业务服务。"""

from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.mapping_stock_concept import MappingStockConcept
from app.repositories.market.stock_concept_repository import StockConceptRepository
from app.schemas.stock_concept import (
    AdminStockConceptCreate,
    AdminStockConceptUpdate,
)


class AdminStockConceptService:
    """后台题材映射管理服务（同花顺同步数据的运营修正入口）。

    同步链路（ths_concept spider）写 source='ths'，此处手工增改写 source='manual'
    以区分数据出处；删除不受来源限制（同步 upsert 幂等，误删可由重跑恢复）。
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = StockConceptRepository(session)

    async def list_concepts(
        self,
        q: str | None = None,
        concept: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """分页查询映射列表，支持股票代码 / 概念关键词过滤。"""
        offset = (page - 1) * page_size
        return await self.repo.list_paged(
            q=q, concept=concept, offset=offset, limit=page_size
        )

    async def create_concept(self, data: AdminStockConceptCreate) -> dict[str, Any]:
        """新增映射，source 标记 manual；(stock_code, concept_code) 冲突时 409。"""
        row = MappingStockConcept(
            stock_code=data.stock_code,
            concept_code=data.concept_code,
            concept_name=data.concept_name,
            source="manual",
        )
        self.session.add(row)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("该股票已存在相同概念代码的映射") from exc
        await self.session.refresh(row)
        return self._to_response(row, await self.repo.get_stock_name(row.stock_code))

    async def update_concept(
        self, concept_id: int, data: AdminStockConceptUpdate
    ) -> dict[str, Any]:
        """更新映射，None 字段不动；改键冲突时 409。"""
        row = await self.repo.get(concept_id)
        if row is None:
            raise NotFoundError(f"Stock concept {concept_id} not found")
        if data.stock_code is not None:
            row.stock_code = data.stock_code
        if data.concept_code is not None:
            row.concept_code = data.concept_code
        if data.concept_name is not None:
            row.concept_name = data.concept_name
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("该股票已存在相同概念代码的映射") from exc
        await self.session.refresh(row)
        return self._to_response(row, await self.repo.get_stock_name(row.stock_code))

    async def delete_concept(self, concept_id: int) -> None:
        """删除单条映射。"""
        row = await self.repo.get(concept_id)
        if row is None:
            raise NotFoundError(f"Stock concept {concept_id} not found")
        await self.session.delete(row)
        await self.session.commit()

    def _to_response(self, row: MappingStockConcept, stock_name: str | None) -> dict[str, Any]:
        return {
            "id": row.id,
            "stock_code": row.stock_code,
            "stock_name": stock_name,
            "concept_code": row.concept_code,
            "concept_name": row.concept_name,
            "source": row.source,
            "updated_at": row.updated_at,
        }
