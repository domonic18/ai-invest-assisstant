"""模拟盘人工交易操作与本地查询服务（多租户：恒按账户读写）。

下单/撤单走 sidecar 实时透传，委托/回报/资金明细由盘后同步链路落库
（``paper_trade_sync``）；报文值转换与行组装分别在 ``paper_trade_converters``
/ ``paper_trade_mappers``。本模块顶层只依赖 sidecar client 与 models，
禁止导入 agent/skills/runtime。
"""

from datetime import date, timedelta
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import today_cn
from app.core.exceptions import BadRequestError, ForbiddenError
from app.models.paper_trade import (
    PaperTradeAccount,
    PaperTradeCashSnapshot,
    PaperTradeExecution,
    PaperTradeOrder,
)
from app.services.trading import account_service
from app.services.trading.client import get_client
from app.services.trading.paper_trade_converters import (
    BARE_CODE_RE,
    bare_stock_code,
    unwrap_rows,
)
from app.services.trading.paper_trade_mappers import (
    normalize_cash_row,
    order_wire_row,
    position_wire_row,
)

# 同步入口经本模块再导出：api 与 collector spider 按 paper_trade_service.sync_* 引用
from app.services.trading.paper_trade_sync import (  # noqa: F401
    sync_account_now,
    sync_daily,
)

logger = structlog.get_logger(__name__)

# stock_basic.market（tushare 主数据，sh/sz/bj）→ 掘金柜台交易所前缀
_MARKET_TO_PREFIX = {"sh": "SHSE", "sz": "SZSE", "bj": "BJSE"}


async def resolve_counter_symbol(session: AsyncSession, symbol_input: str) -> str:
    """平台 6 位代码 → 掘金柜台代码，归属以 ``stock_basic.market`` 主数据为准。

    平台规范标识是裸 6 位 stock_code，柜台前缀（SHSE./SZSE./BJSE.）是掘金适配层
    关注点——柜台对错误前缀（如 SHSE.000037）会静默受理且永不撮合，故归属一律查
    主数据而非代码首位规则；带前缀输入拆码反查主数据做一致性校验。

    Raises:
        BadRequestError: 代码格式非法、主数据无此代码或前缀与归属市场不符。
    """
    from app.services.market import stock_service

    raw = symbol_input.strip().upper()
    code = raw.split(".", 1)[1] if "." in raw else raw
    if not BARE_CODE_RE.fullmatch(code):
        raise BadRequestError(f"无法识别的代码：{symbol_input}（应为 6 位股票代码）")
    stock = await stock_service.get_stock_by_code(session, code)
    if stock is None or not stock.market:
        raise BadRequestError(f"系统主数据中无代码 {code}，请确认后重试")
    prefix = _MARKET_TO_PREFIX.get(stock.market.lower())
    if prefix is None:
        raise BadRequestError(f"代码 {code} 归属市场 {stock.market} 暂不支持")
    if "." in raw and raw != f"{prefix}.{code}":
        raise BadRequestError(
            f"{code} 属{prefix}（主数据 market={stock.market}），应输入 {prefix}.{code} 或 {code}"
        )
    return f"{prefix}.{code}"


async def get_overview(session: AsyncSession, account: PaperTradeAccount) -> dict[str, Any]:
    """实时总览透传（资金 / 持仓 / 未结委托），不落库。

    持仓可用数做 T+1 修正：掘金仿真 available 把当日买入计入可卖（与 A 股
    T+1 规则不符），此处扣减本地今日已成交买入量，下限 0。

    Raises:
        PaperTradeNotConfiguredError: paper_trade_url 未配置。
        PaperTradeGatewayError: sidecar 或柜台错误。
    """
    client = get_client()
    credentials = account_service.credentials_for(account)
    today = today_cn()
    cash_row = normalize_cash_row(await client.get_cash(credentials), today)
    cash_wire = {
        key: float(value) if value is not None else None
        for key, value in cash_row.items()
        if key != "trade_date"
    }
    bought_today = await _bought_today_by_code(session, account.id, today)
    positions = []
    for row in unwrap_rows(await client.get_positions(credentials)):
        position = position_wire_row(row)
        available = position.get("available_volume")
        bought = bought_today.get(str(position.get("stock_code")), 0)
        if available is not None and bought:
            position["available_volume"] = max(0, available - bought)
        positions.append(position)
    return {
        "enabled": True,
        "cash": cash_wire,
        "positions": positions,
        "unfinished_orders": [
            order_wire_row(row, today)
            for row in unwrap_rows(await client.get_unfinished_orders(credentials))
        ],
    }


async def _bought_today_by_code(
    session: AsyncSession, account_id: int, trade_date: date
) -> dict[str, int]:
    """本地已成交买入按标的聚合（T+1 修正的扣减量，symbol 后缀为 6 位代码）。"""
    result = await session.execute(
        select(
            PaperTradeExecution.symbol,
            func.coalesce(func.sum(PaperTradeExecution.volume), 0),
        ).where(
            PaperTradeExecution.paper_trade_account_id == account_id,
            PaperTradeExecution.trade_date == trade_date,
            PaperTradeExecution.side == 1,
        )
        .group_by(PaperTradeExecution.symbol)
    )
    return {bare_stock_code(sym): int(vol or 0) for sym, vol in result.all()}


def _ensure_manual_tradable(account: PaperTradeAccount) -> None:
    """人工交易守卫：agent 专属账户与停用账户一律 403（与前端禁用态同契约）。"""
    if account.agent_key is not None:
        raise ForbiddenError("agent 专属账户禁止人工操作")
    if not account.is_enabled:
        raise ForbiddenError("账户已停用，请先在管理后台或账户配置中启用")


async def place_order(
    session: AsyncSession,
    account: PaperTradeAccount,
    *,
    symbol: str,
    side: str,
    volume: int,
    price: float = 0.0,
    order_type: str = "limit",
) -> Any:
    """人工下单（agent 专属/已停用账户 403）；柜台响应原样返回，委托明细待盘后/轮询落库。

    symbol 为平台 6 位代码（或带柜台前缀的完整代码），经主数据解析为柜台代码。

    Raises:
        ForbiddenError: 目标账户是 agent 专属账户或已停用。
        BadRequestError: 代码无法识别、主数据无此代码或前缀与归属市场不符。
        PaperTradeNotConfiguredError: paper_trade_url 未配置。
        PaperTradeGatewayError: sidecar 或柜台错误（含拒单）。
    """
    _ensure_manual_tradable(account)
    counter_symbol = await resolve_counter_symbol(session, symbol)
    client = get_client()
    return await client.place_order(
        account_service.credentials_for(account),
        counter_symbol,
        side,
        volume,
        price=price,
        order_type=order_type,
    )


async def cancel_order(account: PaperTradeAccount, cl_ord_id: str) -> Any:
    """人工撤单（agent 专属/已停用账户 403）；柜台按 accountId+clOrdId 校验归属。"""
    _ensure_manual_tradable(account)
    client = get_client()
    return await client.cancel_order(account_service.credentials_for(account), cl_ord_id)


async def get_orders(
    session: AsyncSession,
    account_id: int,
    trade_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[PaperTradeOrder], date, int]:
    """按账户 + 业务日分页查本地委托（id 升序 = 落库顺序）；日期缺省取最近交易日。"""
    from app.services.market import trade_calendar_service

    resolved = trade_date or await trade_calendar_service.resolve_latest_trade_date(
        session
    )
    total = await session.scalar(
        select(func.count())
        .select_from(PaperTradeOrder)
        .where(
            PaperTradeOrder.paper_trade_account_id == account_id,
            PaperTradeOrder.trade_date == resolved,
        )
    )
    result = await session.execute(
        select(PaperTradeOrder)
        .where(
            PaperTradeOrder.paper_trade_account_id == account_id,
            PaperTradeOrder.trade_date == resolved,
        )
        .order_by(PaperTradeOrder.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.scalars().all()), resolved, int(total or 0)


async def get_executions(
    session: AsyncSession,
    account_id: int,
    trade_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[PaperTradeExecution], date, int]:
    """按账户 + 业务日分页查本地成交回报；日期缺省取最近交易日。"""
    from app.services.market import trade_calendar_service

    resolved = trade_date or await trade_calendar_service.resolve_latest_trade_date(
        session
    )
    total = await session.scalar(
        select(func.count())
        .select_from(PaperTradeExecution)
        .where(
            PaperTradeExecution.paper_trade_account_id == account_id,
            PaperTradeExecution.trade_date == resolved,
        )
    )
    result = await session.execute(
        select(PaperTradeExecution)
        .where(
            PaperTradeExecution.paper_trade_account_id == account_id,
            PaperTradeExecution.trade_date == resolved,
        )
        .order_by(PaperTradeExecution.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.scalars().all()), resolved, int(total or 0)


async def get_nav_history(
    session: AsyncSession, account_id: int, days: int = 30
) -> list[PaperTradeCashSnapshot]:
    """账户最近 N 个交易日的资金快照（按 trade_date 升序返回）。"""
    result = await session.execute(
        select(PaperTradeCashSnapshot)
        .where(PaperTradeCashSnapshot.paper_trade_account_id == account_id)
        .order_by(PaperTradeCashSnapshot.trade_date.desc())
        .limit(days)
    )
    return list(reversed(result.scalars().all()))


TRADE_MARKER_MAX_ROWS = 500


async def get_trade_markers(
    session: AsyncSession, user_id: int, stock_code: str, days: int = 120
) -> list[PaperTradeExecution]:
    """当前用户全部账户在最近 N 个自然日内对指定标的的成交回报（trade_date 升序）。

    用于个股图表 B/S/T 标记；成交表无 stock_code 列，按柜台 symbol 点号后缀过滤。
    """
    code = stock_code.strip()
    if not BARE_CODE_RE.fullmatch(code):
        raise BadRequestError(f"无效的股票代码：{stock_code}（应为 6 位代码）")
    start = today_cn() - timedelta(days=days)
    result = await session.execute(
        select(PaperTradeExecution)
        .join(
            PaperTradeAccount,
            PaperTradeAccount.id == PaperTradeExecution.paper_trade_account_id,
        )
        .where(
            PaperTradeAccount.user_id == user_id,
            PaperTradeExecution.symbol.like(f"%.{code}"),
            PaperTradeExecution.trade_date >= start,
        )
        .order_by(PaperTradeExecution.trade_date, PaperTradeExecution.id)
        .limit(TRADE_MARKER_MAX_ROWS)
    )
    return list(result.scalars().all())
