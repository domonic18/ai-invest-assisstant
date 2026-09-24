"""模拟盘 API 路由（总览实时透传 + 本地三表只读查询）。"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.pagination import DEFAULT_PAGE, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.paper_trade import (
    PaperTradeExecutionPageResponse,
    PaperTradeExecutionRow,
    PaperTradeNavPoint,
    PaperTradeNavResponse,
    PaperTradeOrderPageResponse,
    PaperTradeOrderRow,
    PaperTradeOverviewResponse,
)
from app.services.trading import paper_trade_service
from app.services.trading.errors import PaperTradeNotConfiguredError

router = APIRouter()


@router.get("/overview", response_model=PaperTradeOverviewResponse)
async def get_overview(
    current_user: Annotated[User, Depends(get_current_user)],
) -> PaperTradeOverviewResponse:
    """实时总览（资金/持仓/未结委托）；未配置返回 enabled=false 引导卡而非报错。"""
    try:
        payload = await paper_trade_service.get_overview()
    except PaperTradeNotConfiguredError:
        return PaperTradeOverviewResponse(enabled=False)
    return PaperTradeOverviewResponse.model_validate(payload)


@router.get("/orders", response_model=PaperTradeOrderPageResponse)
async def list_orders(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    trade_date: date | None = None,
    page: int = Query(DEFAULT_PAGE, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> PaperTradeOrderPageResponse:
    """本地委托分页（业务日缺省取最近交易日，id 升序 = 落库顺序）。"""
    rows, resolved, total = await paper_trade_service.get_orders(
        session, trade_date, page, page_size
    )
    return PaperTradeOrderPageResponse(
        total=total,
        page=page,
        page_size=page_size,
        trade_date=resolved,
        items=[PaperTradeOrderRow.model_validate(row) for row in rows],
    )


@router.get("/executions", response_model=PaperTradeExecutionPageResponse)
async def list_executions(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    trade_date: date | None = None,
    page: int = Query(DEFAULT_PAGE, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> PaperTradeExecutionPageResponse:
    """本地成交回报分页（业务日缺省取最近交易日）。"""
    rows, resolved, total = await paper_trade_service.get_executions(
        session, trade_date, page, page_size
    )
    return PaperTradeExecutionPageResponse(
        total=total,
        page=page,
        page_size=page_size,
        trade_date=resolved,
        items=[PaperTradeExecutionRow.model_validate(row) for row in rows],
    )


@router.get("/nav", response_model=PaperTradeNavResponse)
async def get_nav_curve(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    days: int = Query(30, ge=1, le=365, description="最近 N 个交易日"),
) -> PaperTradeNavResponse:
    """净值曲线（快照表，trade_date 升序）。"""
    rows = await paper_trade_service.get_nav_history(session, days)
    return PaperTradeNavResponse(
        items=[PaperTradeNavPoint.model_validate(row) for row in rows]
    )
