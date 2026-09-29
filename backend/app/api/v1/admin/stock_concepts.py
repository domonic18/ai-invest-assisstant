"""管理后台题材（股票-概念）映射 API 端点。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.pagination import DEFAULT_PAGE, DEFAULT_PAGE_SIZE
from app.dependencies import get_current_admin_user, get_db
from app.schemas.stock import PaginatedResponse
from app.schemas.stock_concept import (
    AdminStockConceptCreate,
    AdminStockConceptResponse,
    AdminStockConceptUpdate,
)
from app.services.admin.stock_concepts import AdminStockConceptService

router = APIRouter(dependencies=[Depends(get_current_admin_user)])


@router.get("/", response_model=PaginatedResponse)
async def list_stock_concepts(
    session: Annotated[AsyncSession, Depends(get_db)],
    q: Annotated[str | None, Query(max_length=10)] = None,
    concept: Annotated[str | None, Query(max_length=100)] = None,
    page: int = DEFAULT_PAGE,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> PaginatedResponse:
    """分页查询题材映射，支持股票代码（q）与概念关键词（concept）过滤。"""
    items, total = await AdminStockConceptService(session).list_concepts(
        q, concept, page, page_size
    )
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[AdminStockConceptResponse.model_validate(item) for item in items],
    )


@router.post(
    "/",
    response_model=AdminStockConceptResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_stock_concept(
    data: AdminStockConceptCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AdminStockConceptResponse:
    """新增题材映射（source=manual，唯一键冲突 409）。"""
    item = await AdminStockConceptService(session).create_concept(data)
    return AdminStockConceptResponse.model_validate(item)


@router.put("/{concept_id}", response_model=AdminStockConceptResponse)
async def update_stock_concept(
    concept_id: int,
    data: AdminStockConceptUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AdminStockConceptResponse:
    """更新题材映射（改键冲突 409）。"""
    item = await AdminStockConceptService(session).update_concept(concept_id, data)
    return AdminStockConceptResponse.model_validate(item)


@router.delete("/{concept_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stock_concept(
    concept_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """删除题材映射。"""
    await AdminStockConceptService(session).delete_concept(concept_id)
