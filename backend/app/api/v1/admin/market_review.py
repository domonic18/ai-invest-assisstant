"""管理后台大盘复盘管理 API 端点。"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnprocessableEntityError
from app.dependencies import get_current_admin_user, get_db
from app.schemas.market import (
    AdminMarketReviewCreateRequest,
    AdminMarketReviewSectionsRequest,
    AdminSectionDefinition,
    MarketReviewResponse,
)
from app.schemas.stock import PaginatedResponse
from app.services.admin.market_review import AdminMarketReviewService

router = APIRouter(dependencies=[Depends(get_current_admin_user)])


@router.get("/section-definitions", response_model=list[AdminSectionDefinition])
async def get_section_definitions() -> list[AdminSectionDefinition]:
    """复盘分区定义（手动填写表单的动态数据源）。

    声明在 ``GET /{trade_date}`` 之前，避免路径被日期参数路由吞掉。
    """
    return AdminMarketReviewService.section_definitions()


@router.get("/", response_model=PaginatedResponse)
async def list_market_reviews(
    session: Annotated[AsyncSession, Depends(get_db)],
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse:
    """分页返回每个交易日最新一条复盘的元信息。"""
    items, total = await AdminMarketReviewService(session).list_reviews(
        page, page_size, start_date, end_date
    )
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )


@router.post(
    "/",
    response_model=MarketReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_market_review(
    data: AdminMarketReviewCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MarketReviewResponse:
    """手动创建指定交易日复盘（sections 缺分区/为空返回 422）。"""
    service = AdminMarketReviewService(session)
    try:
        return await service.create_manual(data.trade_date, data.sections)
    except ValueError as exc:
        raise UnprocessableEntityError(str(exc)) from exc


@router.get("/{trade_date}", response_model=MarketReviewResponse)
async def get_market_review(
    trade_date: date,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MarketReviewResponse:
    """读取指定交易日最新一条复盘的完整分区内容。"""
    return await AdminMarketReviewService(session).get_detail(trade_date)


@router.put("/{trade_date}", response_model=MarketReviewResponse)
async def update_market_review(
    trade_date: date,
    data: AdminMarketReviewSectionsRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MarketReviewResponse:
    """以新记录覆盖指定交易日复盘内容（旧行保留作历史）。"""
    service = AdminMarketReviewService(session)
    try:
        return await service.update_sections(trade_date, data.sections)
    except ValueError as exc:
        raise UnprocessableEntityError(str(exc)) from exc


@router.delete("/{trade_date}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_market_review(
    trade_date: date,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """删除该交易日全部生成记录（用户编辑副本保留）。"""
    await AdminMarketReviewService(session).delete(trade_date)
