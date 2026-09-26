"""模拟盘盘后同步链路（多租户：恒按账户读写）。

16:00 盘后（或手动）按启用账户逐一拉取掘金仿真当日委托/成交回报/资金概况，
幂等 upsert 三表：委托按（账户, cl_ord_id）冲突更新状态，回报按（账户, exec_id）
冲突跳过（不可变），资金按（账户, trade_date）冲突覆盖。账户间错误隔离
（单账户失败写 last_error 不影响其他账户）；``redis_lock`` 防并发；写操作显式 commit。
本模块顶层只依赖 sidecar client 与 models，禁止导入 agent/skills/runtime。
"""

from datetime import date
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_now
from app.core.exceptions import ConflictError
from app.core.locking import DEFAULT_LOCK_TTL_SECONDS, redis_lock
from app.models.paper_trade import (
    PaperTradeAccount,
    PaperTradeCashSnapshot,
    PaperTradeExecution,
    PaperTradeOrder,
)
from app.services.trading import account_service
from app.services.trading.client import PaperTradeClient, get_client
from app.services.trading.errors import PaperTradeNotConfiguredError
from app.services.trading.paper_trade_mappers import (
    normalize_cash_row,
    normalize_execution_rows,
    normalize_order_rows,
)

logger = structlog.get_logger(__name__)

SYNC_LOCK_KEY = "paper-trade-sync"


async def _upsert_orders(
    session: AsyncSession, rows: list[dict[str, Any]]
) -> int:
    if not rows:
        return 0
    stmt = pg_insert(PaperTradeOrder).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            PaperTradeOrder.paper_trade_account_id,
            PaperTradeOrder.cl_ord_id,
        ],
        set_={
            "status": stmt.excluded.status,
            "ord_rej_reason": stmt.excluded.ord_rej_reason,
            "ord_rej_reason_detail": stmt.excluded.ord_rej_reason_detail,
            "counter_updated_at": stmt.excluded.counter_updated_at,
            "raw": stmt.excluded.raw,
            "updated_at": utc_now(),
        },
    )
    await session.execute(stmt)
    return len(rows)


async def _insert_executions(
    session: AsyncSession, rows: list[dict[str, Any]]
) -> int:
    """回报不可变，冲突即跳过。"""
    if not rows:
        return 0
    stmt = pg_insert(PaperTradeExecution).values(rows)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=[
            PaperTradeExecution.paper_trade_account_id,
            PaperTradeExecution.exec_id,
        ]
    )
    await session.execute(stmt)
    return len(rows)


async def _upsert_cash(
    session: AsyncSession, row: dict[str, Any]
) -> None:
    stmt = pg_insert(PaperTradeCashSnapshot).values([row])
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            PaperTradeCashSnapshot.paper_trade_account_id,
            PaperTradeCashSnapshot.trade_date,
        ],
        set_={
            "nav": stmt.excluded.nav,
            "available": stmt.excluded.available,
            "balance": stmt.excluded.balance,
            "cum_inout": stmt.excluded.cum_inout,
            "last_inout": stmt.excluded.last_inout,
            "updated_at": utc_now(),
        },
    )
    await session.execute(stmt)


async def _sync_one_account(
    session: AsyncSession,
    client: PaperTradeClient,
    account: account_service.AccountRef,
    resolved: date,
) -> dict[str, Any]:
    """单账户当日委托/成交/资金拉取并幂等落库（不 commit，事务边界归调用方）。"""
    credentials = account_service.credentials_for(account)
    order_rows = normalize_order_rows(
        await client.get_intraday_orders(credentials),
        resolved,
        account_id=account.id,
        order_source=(
            account_service.ORDER_SOURCE_AGENT
            if account.agent_key is not None
            else account_service.ORDER_SOURCE_MANUAL
        ),
    )
    execution_rows = normalize_execution_rows(
        await client.get_intraday_executions(credentials),
        resolved,
        account_id=account.id,
    )
    cash_row = normalize_cash_row(await client.get_cash(credentials), resolved)
    cash_row["paper_trade_account_id"] = account.id

    stored_orders = await _upsert_orders(session, order_rows)
    stored_executions = await _insert_executions(session, execution_rows)
    await _upsert_cash(session, cash_row)
    return {
        "orders": stored_orders,
        "executions": stored_executions,
        # float 而非 Decimal：summary 会进 collector_log.metadata（JSONB）
        "nav": float(cash_row["nav"]) if cash_row["nav"] is not None else None,
    }


async def _stamp_account_synced(session: AsyncSession, account_id: int, *, error: str | None) -> None:
    """回写账户同步状态（列 Row 循环里 ORM 属性不可用，走 core UPDATE）。"""
    await session.execute(
        update(PaperTradeAccount)
        .where(PaperTradeAccount.id == account_id)
        .values(last_error=error, last_synced_at=utc_now())
    )


async def sync_daily(
    session: AsyncSession, trade_date: date | None = None
) -> dict[str, Any]:
    """按启用账户逐一拉取掘金仿真当日委托/成交/资金，幂等 upsert 三表。

    Args:
        session: 数据库会话（写操作显式 commit，账户间错误隔离）。
        trade_date: 业务日；缺省取最近交易日（周末手动补跑不落空）。

    Returns:
        同步摘要 {trade_date, accounts, orders, executions, failed, details}。

    Raises:
        PaperTradeNotConfiguredError: paper_trade_url 未配置或无启用账户。
        ConflictError: 其他实例正在同步。
        PaperTradeGatewayError: sidecar 或柜台错误。
    """
    client = get_client()

    # 延迟 import：market 子域聚合面大，避免顶层环导入
    from app.services.market import trade_calendar_service

    resolved = trade_date or await trade_calendar_service.resolve_latest_trade_date(
        session
    )

    # 列 Row 而非 ORM 实体：循环内 per-account rollback 会使 identity map 整体过期，
    # 后续账户的属性访问会触发同步上下文外的隐式 lazy load（greenlet 崩溃）
    accounts_result = await session.execute(
        select(
            PaperTradeAccount.id,
            PaperTradeAccount.name,
            PaperTradeAccount.agent_key,
            PaperTradeAccount.counter_account_id,
            PaperTradeAccount.token_encrypted,
        )
        .where(PaperTradeAccount.is_enabled.is_(True))
        .order_by(PaperTradeAccount.id)
    )
    accounts = list(accounts_result.all())
    if not accounts:
        raise PaperTradeNotConfiguredError("暂无启用的模拟盘账户，请先在模拟交易页配置")

    async with redis_lock(SYNC_LOCK_KEY, ttl=DEFAULT_LOCK_TTL_SECONDS) as acquired:
        if not acquired:
            raise ConflictError("模拟盘盘后同步正在执行，请稍后重试")
        details: list[dict[str, Any]] = []
        total_orders = 0
        total_executions = 0
        failed = 0
        for account in accounts:
            outcome: dict[str, Any] = {
                "account_id": account.id,
                "name": account.name,
                "agent_key": account.agent_key,
            }
            try:
                result = await _sync_one_account(session, client, account, resolved)
                await _stamp_account_synced(session, account.id, error=None)
                await session.commit()
                total_orders += result["orders"]
                total_executions += result["executions"]
                outcome.update(**result, error=None)
            except Exception as exc:  # noqa: BLE001 —— 账户间错误隔离，失败不阻断其他账户
                await session.rollback()
                failed += 1
                await _stamp_account_synced(session, account.id, error=str(exc)[:500])
                await session.commit()
                outcome.update(orders=0, executions=0, nav=None, error=str(exc)[:200])
                logger.warning(
                    "paper_trade_sync_account_failed",
                    account_id=account.id,
                    error=str(exc),
                )
            details.append(outcome)

    summary = {
        "trade_date": resolved.isoformat(),
        "accounts": len(accounts),
        "orders": total_orders,
        "executions": total_executions,
        "failed": failed,
        "details": details,
    }
    logger.info("paper_trade_synced", **summary)
    return summary


async def sync_account_now(
    session: AsyncSession, account: PaperTradeAccount
) -> dict[str, Any]:
    """单账户即时同步（人工下单/撤单后调用，本地委托历史即时反映柜台状态）。

    Raises:
        ConflictError: 盘后批量同步或另一即时同步正在执行。
        PaperTradeNotConfiguredError: paper_trade_url 未配置。
        PaperTradeGatewayError: sidecar 或柜台错误（向上传播给用户）。
    """
    client = get_client()

    # 延迟 import：market 子域聚合面大，避免顶层环导入
    from app.services.market import trade_calendar_service

    resolved = await trade_calendar_service.resolve_latest_trade_date(session)

    async with redis_lock(SYNC_LOCK_KEY, ttl=DEFAULT_LOCK_TTL_SECONDS) as acquired:
        if not acquired:
            raise ConflictError("模拟盘同步正在执行，请稍后重试")
        result = await _sync_one_account(session, client, account, resolved)
        await _stamp_account_synced(session, account.id, error=None)
        await session.commit()

    summary = {
        "trade_date": resolved.isoformat(),
        "account_id": account.id,
        **result,
    }
    logger.info("paper_trade_account_synced", **summary)
    return summary
