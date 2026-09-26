"""模拟盘账户配置服务（多租户：每用户自有掘金仿真凭证）。

token Fernet 加密落库（utils/crypto 同源，proxy_configs 先例）；
counter_account_id 全平台唯一（防 token 共享/多头配置）；每 Agent 至多绑定
一个专属账户（部分唯一索引兜底并发，agent-hub-plan.md D22）；每用户账户数
上限防滥用。账户删除仅在无交易数据时允许（数据保留以供复盘）。
查询恒按账户过滤，NULL 账户维度的存量行不可见（docs/plan/paper-trading-plan.md §6）。
"""

from typing import Protocol

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.models.paper_trade import (
    PaperTradeAccount,
    PaperTradeCashSnapshot,
    PaperTradeExecution,
    PaperTradeOrder,
)
from app.services.trading.client import CounterCredentials
from app.services.trading.errors import AgentAccountNotDesignatedError
from app.utils.crypto import decrypt_token, encrypt_token

logger = structlog.get_logger(__name__)

MAX_ACCOUNTS_PER_USER = 10

# 委托来源标记（order_source）：agent 账户的委托 = agent 下单，其余 = 人工
ORDER_SOURCE_MANUAL = "manual"
ORDER_SOURCE_AGENT = "agent"


class AccountRef(Protocol):
    """同步链路可用的最小账户结构（sync 列 Row 或 ORM 实体均满足）。"""

    id: int
    name: str
    agent_key: str | None
    token_encrypted: str
    counter_account_id: str


def credentials_for(account: AccountRef) -> CounterCredentials:
    """解密账户凭证为柜台调用参数（明文仅在调用链内存中传递）。"""
    return CounterCredentials(
        token=decrypt_token(account.token_encrypted),
        account_id=account.counter_account_id,
    )


async def list_accounts(
    session: AsyncSession, user_id: int
) -> list[PaperTradeAccount]:
    """用户自有账户列表（id 升序 = 配置顺序）。"""
    result = await session.execute(
        select(PaperTradeAccount)
        .where(PaperTradeAccount.user_id == user_id)
        .order_by(PaperTradeAccount.id)
    )
    return list(result.scalars().all())


async def resolve_for_user(
    session: AsyncSession, user_id: int, account_id: int
) -> PaperTradeAccount:
    """按租户解析账户：不存在或不属于该用户一律 404（不泄露存在性）。"""
    account = await session.get(PaperTradeAccount, account_id)
    if account is None or account.user_id != user_id:
        raise NotFoundError("模拟盘账户不存在")
    return account


async def resolve_agent_account(
    session: AsyncSession, agent_key: str
) -> PaperTradeAccount:
    """解析指定 Agent 的专属账户（``agent_key`` 唯一绑定，D22）。

    对话交易工具与定时执行（批次 6-8）共用此入口；未绑定时抛
    ``AgentAccountNotDesignatedError``（工具层捕获转引导文案）。
    """
    account = await session.scalar(
        select(PaperTradeAccount).where(PaperTradeAccount.agent_key == agent_key)
    )
    if account is None:
        raise AgentAccountNotDesignatedError(agent_key)
    return account


async def create_account(
    session: AsyncSession,
    user_id: int,
    *,
    name: str,
    token: str,
    counter_account_id: str,
) -> PaperTradeAccount:
    """新增账户配置：token 加密落库，counter_account_id 冲突 409。"""
    duplicate = await session.scalar(
        select(PaperTradeAccount).where(
            PaperTradeAccount.counter_account_id == counter_account_id
        )
    )
    if duplicate is not None:
        raise ConflictError("该掘金柜台账户已被绑定（counter_account_id 全平台唯一）")
    count = await session.scalar(
        select(func.count())
        .select_from(PaperTradeAccount)
        .where(PaperTradeAccount.user_id == user_id)
    )
    if int(count or 0) >= MAX_ACCOUNTS_PER_USER:
        raise ConflictError(f"每个用户最多配置 {MAX_ACCOUNTS_PER_USER} 个模拟盘账户")
    account = PaperTradeAccount(
        user_id=user_id,
        name=name,
        token_encrypted=encrypt_token(token),
        counter_account_id=counter_account_id,
    )
    session.add(account)
    await session.commit()
    await session.refresh(account)
    return account


async def update_account(
    session: AsyncSession,
    user_id: int,
    account_id: int,
    *,
    name: str | None = None,
    token: str | None = None,
    counter_account_id: str | None = None,
) -> PaperTradeAccount:
    """更新账户配置（token 变更时重新加密；counter_account_id 换绑查重）。"""
    account = await resolve_for_user(session, user_id, account_id)
    if counter_account_id and counter_account_id != account.counter_account_id:
        duplicate = await session.scalar(
            select(PaperTradeAccount).where(
                PaperTradeAccount.counter_account_id == counter_account_id
            )
        )
        if duplicate is not None:
            raise ConflictError("该掘金柜台账户已被绑定（counter_account_id 全平台唯一）")
        account.counter_account_id = counter_account_id
    if name:
        account.name = name
    if token:
        account.token_encrypted = encrypt_token(token)
    await session.commit()
    await session.refresh(account)
    return account


async def delete_account(session: AsyncSession, user_id: int, account_id: int) -> None:
    """删除账户配置；已有交易数据（委托/回报/快照）时拒绝。"""
    account = await resolve_for_user(session, user_id, account_id)
    for model in (PaperTradeOrder, PaperTradeExecution, PaperTradeCashSnapshot):
        existing = await session.scalar(
            select(model.id)
            .where(model.paper_trade_account_id == account_id)  # type: ignore[attr-defined]
            .limit(1)
        )
        if existing is not None:
            raise ConflictError("该账户已有交易数据，禁止删除（数据保留以供复盘）")
    await session.delete(account)
    await session.commit()
    logger.info("paper_trade_account_deleted", account_id=account_id, user_id=user_id)


async def admin_list_accounts(session: AsyncSession) -> list[PaperTradeAccount]:
    """全平台账户列表（管理端，按 user_id + id 排序）。"""
    result = await session.execute(
        select(PaperTradeAccount).order_by(
            PaperTradeAccount.user_id, PaperTradeAccount.id
        )
    )
    return list(result.scalars().all())


async def admin_designate_agent(
    session: AsyncSession, account_id: int, agent_key: str
) -> PaperTradeAccount:
    """为指定 Agent 绑定专属账户：先清后设（部分唯一索引兜底并发）。

    Raises:
        NotFoundError: 账户或 Agent 不存在。
    """
    account = await session.get(PaperTradeAccount, account_id)
    if account is None:
        raise NotFoundError("模拟盘账户不存在")
    from app.services.trading.agent_registry import get_agent

    await get_agent(session, agent_key)
    if account.agent_key != agent_key:
        current = await session.scalar(
            select(PaperTradeAccount).where(PaperTradeAccount.agent_key == agent_key)
        )
        if current is not None:
            current.agent_key = None
        account.agent_key = agent_key
        await session.commit()
    return account


async def admin_clear_agent(
    session: AsyncSession, account_id: int, agent_key: str
) -> PaperTradeAccount:
    """解除 Agent 专属账户绑定：解除后该 Agent 无关联账户，可随时重新指定。"""
    account = await session.get(PaperTradeAccount, account_id)
    if account is None:
        raise NotFoundError("模拟盘账户不存在")
    if account.agent_key != agent_key:
        raise BadRequestError("该账户未绑定此 Agent，无需解除")
    account.agent_key = None
    await session.commit()
    logger.info(
        "paper_trade_agent_cleared", account_id=account_id, agent_key=agent_key
    )
    return account


async def admin_set_enabled(
    session: AsyncSession, account_id: int, enabled: bool
) -> PaperTradeAccount:
    """启用/停用账户（停用后盘后同步跳过，页面仍可读本地历史数据）。"""
    account = await session.get(PaperTradeAccount, account_id)
    if account is None:
        raise NotFoundError("模拟盘账户不存在")
    if account.is_enabled != enabled:
        account.is_enabled = enabled
        await session.commit()
    return account
