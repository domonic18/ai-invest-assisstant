"""模拟盘 API 路由（账户配置 CRUD + 总览实时透传 + 本地三表查询 + 人工下单/撤单）。

多租户：读端点恒带 account_id（resolve_for_user 保证跨租户 404）；
agent 专属账户禁止人工下单/撤单（服务层 403）。
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.pagination import DEFAULT_PAGE, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.dependencies import get_current_user, get_db
from app.models.paper_trade import PaperTradeAccount, PaperTradeExecution
from app.models.user import User
from app.schemas.paper_trade import (
    PaperTradeAccountCreateRequest,
    PaperTradeAccountListResponse,
    PaperTradeAccountRow,
    PaperTradeAccountSyncResponse,
    PaperTradeAccountUpdateRequest,
    PaperTradeActionResponse,
    PaperTradeExecutionPageResponse,
    PaperTradeExecutionRow,
    PaperTradeNavPoint,
    PaperTradeNavResponse,
    PaperTradeOrderPageResponse,
    PaperTradeOrderRow,
    PaperTradeOverviewResponse,
    PaperTradePlaceOrderRequest,
    PaperTradeTradeMarkerResponse,
    PaperTradeTradeMarkerRow,
)
from app.services.trading import account_service, paper_trade_service
from app.services.trading.errors import PaperTradeNotConfiguredError
from app.utils.crypto import decrypt_token, mask_token

router = APIRouter()


def _account_row(account: PaperTradeAccount) -> PaperTradeAccountRow:
    """账户 ORM → wire 行（token 只回掩码，明文不出库）。"""
    return PaperTradeAccountRow(
        id=account.id,
        name=account.name,
        counter_account_id=account.counter_account_id,
        agent_key=account.agent_key,
        is_enabled=account.is_enabled,
        token_masked=mask_token(decrypt_token(account.token_encrypted)),
        last_error=account.last_error,
        last_synced_at=account.last_synced_at,
        created_at=account.created_at,
    )


def _execution_row(execution: PaperTradeExecution) -> PaperTradeExecutionRow:
    """成交 ORM → wire 行；存量行缺成交额时按 价×量 补算（回报不可变无法回填）。"""
    row = PaperTradeExecutionRow.model_validate(execution)
    if row.turnover is None and row.price is not None and row.volume:
        row.turnover = float(
            (Decimal(str(row.price)) * row.volume).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        )
    return row


# ============================================================
# 账户配置
# ============================================================


@router.get("/accounts", response_model=PaperTradeAccountListResponse)
async def list_accounts(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PaperTradeAccountListResponse:
    """当前用户的模拟盘账户列表（token 掩码）。"""
    accounts = await account_service.list_accounts(session, current_user.id)
    return PaperTradeAccountListResponse(
        items=[_account_row(account) for account in accounts]
    )


@router.post(
    "/accounts",
    response_model=PaperTradeAccountRow,
    status_code=status.HTTP_201_CREATED,
)
async def create_account(
    request: PaperTradeAccountCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PaperTradeAccountRow:
    """新增账户配置（counter_account_id 全平台唯一，冲突 409）。"""
    account = await account_service.create_account(
        session,
        current_user.id,
        name=request.name,
        token=request.token,
        counter_account_id=request.counter_account_id,
    )
    return _account_row(account)


@router.put("/accounts/{account_id}", response_model=PaperTradeAccountRow)
async def update_account(
    account_id: int,
    request: PaperTradeAccountUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PaperTradeAccountRow:
    """更新账户配置（未提供的字段不变；token 变更重新加密）。"""
    account = await account_service.update_account(
        session,
        current_user.id,
        account_id,
        name=request.name,
        token=request.token,
        counter_account_id=request.counter_account_id,
    )
    return _account_row(account)


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """删除账户配置（已有交易数据时 409 拒绝）。"""
    await account_service.delete_account(session, current_user.id, account_id)


@router.post("/accounts/{account_id}/sync", response_model=PaperTradeAccountSyncResponse)
async def sync_account(
    account_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PaperTradeAccountSyncResponse:
    """单账户即时同步（人工下单/撤单后前端调用，本地委托历史即时反映柜台状态）。"""
    account = await account_service.resolve_for_user(session, current_user.id, account_id)
    summary = await paper_trade_service.sync_account_now(session, account)
    return PaperTradeAccountSyncResponse(
        trade_date=summary["trade_date"],
        account_id=summary["account_id"],
        orders=summary["orders"],
        executions=summary["executions"],
        nav=summary["nav"],
    )


# ============================================================
# 行情与交易查询（恒按账户）
# ============================================================


@router.get("/overview", response_model=PaperTradeOverviewResponse)
async def get_overview(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    account_id: int = Query(..., description="模拟盘账户 ID"),
) -> PaperTradeOverviewResponse:
    """账户实时总览（资金/持仓/未结委托）；功能未配置返回 enabled=false 引导卡。"""
    account = await account_service.resolve_for_user(
        session, current_user.id, account_id
    )
    try:
        payload = await paper_trade_service.get_overview(session, account)
    except PaperTradeNotConfiguredError:
        return PaperTradeOverviewResponse(enabled=False)
    return PaperTradeOverviewResponse.model_validate(payload)


@router.get("/orders", response_model=PaperTradeOrderPageResponse)
async def list_orders(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    account_id: int = Query(..., description="模拟盘账户 ID"),
    trade_date: date | None = None,
    page: int = Query(DEFAULT_PAGE, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> PaperTradeOrderPageResponse:
    """账户本地委托分页（业务日缺省取最近交易日，id 升序 = 落库顺序）。"""
    await account_service.resolve_for_user(session, current_user.id, account_id)
    rows, resolved, total = await paper_trade_service.get_orders(
        session, account_id, trade_date, page, page_size
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
    account_id: int = Query(..., description="模拟盘账户 ID"),
    trade_date: date | None = None,
    page: int = Query(DEFAULT_PAGE, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> PaperTradeExecutionPageResponse:
    """账户本地成交回报分页（业务日缺省取最近交易日）。"""
    await account_service.resolve_for_user(session, current_user.id, account_id)
    rows, resolved, total = await paper_trade_service.get_executions(
        session, account_id, trade_date, page, page_size
    )
    return PaperTradeExecutionPageResponse(
        total=total,
        page=page,
        page_size=page_size,
        trade_date=resolved,
        items=[_execution_row(row) for row in rows],
    )


@router.get("/nav", response_model=PaperTradeNavResponse)
async def get_nav_curve(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    account_id: int = Query(..., description="模拟盘账户 ID"),
    days: int = Query(30, ge=1, le=365, description="最近 N 个交易日"),
) -> PaperTradeNavResponse:
    """账户净值曲线（快照表，trade_date 升序）。"""
    await account_service.resolve_for_user(session, current_user.id, account_id)
    rows = await paper_trade_service.get_nav_history(session, account_id, days)
    return PaperTradeNavResponse(
        items=[PaperTradeNavPoint.model_validate(row) for row in rows]
    )


@router.get("/trade-markers", response_model=PaperTradeTradeMarkerResponse)
async def list_trade_markers(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    stock_code: str = Query(..., min_length=6, max_length=6, description="6 位股票代码"),
    days: int = Query(120, ge=1, le=730, description="最近 N 个自然日"),
) -> PaperTradeTradeMarkerResponse:
    """当前用户全部账户对该标的的成交回报（个股图表 B/S/T 标记）。"""
    rows = await paper_trade_service.get_trade_markers(
        session, current_user.id, stock_code, days
    )
    return PaperTradeTradeMarkerResponse(
        items=[
            PaperTradeTradeMarkerRow(
                trade_date=row.trade_date,
                counter_created_at=row.counter_created_at,
                side="buy" if row.side == 1 else "sell",
                price=float(row.price) if row.price is not None else None,
                volume=row.volume,
            )
            for row in rows
            if row.side in (1, 2)
        ]
    )


# ============================================================
# 人工交易（agent 专属账户 403）
# ============================================================


@router.post("/orders", response_model=PaperTradeActionResponse)
async def place_order(
    request: PaperTradePlaceOrderRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PaperTradeActionResponse:
    """人工下单（限价单必须带价格；拒单 502 透传柜台原因）。"""
    account = await account_service.resolve_for_user(
        session, current_user.id, request.account_id
    )
    payload: Any = await paper_trade_service.place_order(
        session,
        account,
        symbol=request.symbol,
        side=request.side,
        volume=request.volume,
        price=request.price,
        order_type=request.order_type,
    )
    row = (
        payload[0]
        if isinstance(payload, list) and payload and isinstance(payload[0], dict)
        else {}
    )
    return PaperTradeActionResponse(
        success=True,
        cl_ord_id=str(row.get("cl_ord_id") or ""),
        message="委托已提交",
    )


@router.delete("/orders/{cl_ord_id}", response_model=PaperTradeActionResponse)
async def cancel_order(
    cl_ord_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    account_id: int = Query(..., description="模拟盘账户 ID"),
) -> PaperTradeActionResponse:
    """人工撤单（柜台按 accountId + clOrdId 校验归属）。"""
    account = await account_service.resolve_for_user(
        session, current_user.id, account_id
    )
    await paper_trade_service.cancel_order(account, cl_ord_id)
    return PaperTradeActionResponse(success=True, cl_ord_id=cl_ord_id, message="撤单已提交")
