"""管理后台模拟盘账户 API 端点（列表 / 指定 agent 账户 / 启停）。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin_user, get_db
from app.models.paper_trade import PaperTradeAccount
from app.schemas.paper_trade import (
    PaperTradeAdminAccountListResponse,
    PaperTradeAdminAccountRow,
)
from app.services.trading import account_service
from app.utils.crypto import decrypt_token, mask_token

router = APIRouter(
    prefix="/paper-trade",
    dependencies=[Depends(get_current_admin_user)],
)


class AccountEnabledRequest(BaseModel):
    """账户启停请求体。"""

    enabled: bool


def _admin_row(account: PaperTradeAccount) -> PaperTradeAdminAccountRow:
    """账户 ORM → 管理端 wire 行（token 只回掩码）。"""
    return PaperTradeAdminAccountRow(
        id=account.id,
        user_id=account.user_id,
        name=account.name,
        counter_account_id=account.counter_account_id,
        is_agent=account.is_agent,
        is_enabled=account.is_enabled,
        token_masked=mask_token(decrypt_token(account.token_encrypted)),
        last_error=account.last_error,
        last_synced_at=account.last_synced_at,
        created_at=account.created_at,
    )


@router.get("/accounts", response_model=PaperTradeAdminAccountListResponse)
async def list_accounts(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PaperTradeAdminAccountListResponse:
    """全平台模拟盘账户列表（含归属用户）。"""
    accounts = await account_service.admin_list_accounts(session)
    return PaperTradeAdminAccountListResponse(
        items=[_admin_row(account) for account in accounts]
    )


@router.put("/accounts/{account_id}/agent", response_model=PaperTradeAdminAccountRow)
async def designate_agent(
    account_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PaperTradeAdminAccountRow:
    """指定 agent 专属账户（全局唯一，先清后设）。"""
    account = await account_service.admin_designate_agent(session, account_id)
    return _admin_row(account)


@router.delete("/accounts/{account_id}/agent", response_model=PaperTradeAdminAccountRow)
async def clear_agent(
    account_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PaperTradeAdminAccountRow:
    """取消 agent 专属账户指定（解除后 agent 无关联账户，可重新指定）。"""
    account = await account_service.admin_clear_agent(session, account_id)
    return _admin_row(account)


@router.put("/accounts/{account_id}/enabled", response_model=PaperTradeAdminAccountRow)
async def set_enabled(
    account_id: int,
    request: AccountEnabledRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PaperTradeAdminAccountRow:
    """启用/停用账户（停用后盘后同步跳过）。"""
    account = await account_service.admin_set_enabled(session, account_id, request.enabled)
    return _admin_row(account)
