"""Admin stock management API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin_user, get_db
from app.schemas.stock import (
    AdminStockCreate,
    AdminStockUpdate,
    PaginatedResponse,
    StockBasicResponse,
)
from app.services.admin_stock_service import AdminStockService

router = APIRouter(dependencies=[Depends(get_current_admin_user)])


@router.get("/", response_model=PaginatedResponse)
async def list_stocks(
    session: Annotated[AsyncSession, Depends(get_db)],
    q: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> PaginatedResponse:
    """查询股票列表。"""
    items, total = await AdminStockService(session).list_stocks(q, page, page_size)
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[StockBasicResponse.model_validate(item) for item in items],
    )


@router.post("/", response_model=StockBasicResponse, status_code=status.HTTP_201_CREATED)
async def create_stock(
    data: AdminStockCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> StockBasicResponse:
    """创建股票基础信息。"""
    stock = await AdminStockService(session).create_stock(data)
    return StockBasicResponse.model_validate(stock)


@router.get("/{stock_id}", response_model=StockBasicResponse)
async def get_stock(
    stock_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> StockBasicResponse:
    """获取单条股票基础信息。"""
    stock = await AdminStockService(session).get_stock(stock_id)
    if not stock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stock not found",
        )
    return StockBasicResponse.model_validate(stock)


@router.put("/{stock_id}", response_model=StockBasicResponse)
async def update_stock(
    stock_id: int,
    data: AdminStockUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> StockBasicResponse:
    """更新股票基础信息。"""
    stock = await AdminStockService(session).update_stock(stock_id, data)
    if not stock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stock not found",
        )
    return StockBasicResponse.model_validate(stock)


@router.delete("/{stock_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stock(
    stock_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """删除股票基础信息。"""
    try:
        await AdminStockService(session).delete_stock(stock_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
