"""模拟盘盘后同步与本地查询服务（多租户：恒按账户读写）。

16:00 盘后（或手动）按启用账户逐一拉取掘金仿真当日委托/成交回报/资金概况，
幂等 upsert 三表：委托按（账户, cl_ord_id）冲突更新状态，回报按（账户, exec_id）
冲突跳过（不可变），资金按（账户, trade_date）冲突覆盖。账户间错误隔离
（单账户失败写 last_error 不影响其他账户）；``redis_lock`` 防并发；写操作显式 commit。
本模块顶层只依赖 sidecar client 与 models，禁止导入 agent/skills/runtime。
"""

import re
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import CN_TZ, today_cn, utc_now
from app.core.config import get_settings
from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError
from app.core.locking import DEFAULT_LOCK_TTL_SECONDS, redis_lock
from app.models.paper_trade import (
    PaperTradeAccount,
    PaperTradeCashSnapshot,
    PaperTradeExecution,
    PaperTradeOrder,
)
from app.services.trading import account_service
from app.services.trading.client import PaperTradeClient
from app.services.trading.errors import PaperTradeNotConfiguredError

logger = structlog.get_logger(__name__)

SYNC_LOCK_KEY = "paper-trade-sync"

# 回报幂等键：暂定柜台 ex_exec_id，缺失时回退 cl_ord_id+时间组合（实抓字段为准后可回填）
_EXEC_ID_KEYS = ("ex_exec_id", "exec_id")


def _rows(raw: Any) -> list[dict[str, Any]]:
    """柜台列表端点解包后可能为 {}（空结果），统一收敛为 list[dict]。"""
    if not isinstance(raw, list):
        return []
    return [row for row in raw if isinstance(row, dict)]


def _stock_code(symbol: str) -> str:
    """掘金代码 SHSE.600000 → 6 位代码。"""
    return symbol.split(".", 1)[1] if "." in symbol else symbol


_BARE_CODE_RE = re.compile(r"\d{6}")

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
    if not _BARE_CODE_RE.fullmatch(code):
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


def _counter_datetime(value: Any) -> datetime | None:
    """柜台时间字段容错解析：epoch 秒/毫秒或 ISO 字符串 → aware UTC。"""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1e12:  # 毫秒时间戳
            ts /= 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def _cn_trade_date(counter_dt: datetime | None, fallback: date) -> date:
    """业务日 = 柜台时间的 CN 日历日；时间缺失回退同步目标日。"""
    return counter_dt.astimezone(CN_TZ).date() if counter_dt else fallback


def _to_decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _to_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _first(data: dict[str, Any], *keys: str) -> Any:
    """持仓字段多候选键提取（柜台真实字段名待首次成交实抓后收敛）。"""
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


# 柜台（Go sidecar）float32 数值带尾噪声（6.46999979019165），wire 前统一 quantize
_Q_EXP_2 = Decimal("0.01")
_Q_EXP_4 = Decimal("0.0001")


def _q2(value: Decimal | None) -> Decimal | None:
    """金额 quantize 到分（四舍五入）。"""
    return None if value is None else value.quantize(_Q_EXP_2, rounding=ROUND_HALF_UP)


def _q4(value: Decimal | None) -> Decimal | None:
    """价格 quantize 到 0.0001（四舍五入）。"""
    return None if value is None else value.quantize(_Q_EXP_4, rounding=ROUND_HALF_UP)


def _normalize_orders(
    raw: Any,
    fallback_date: date,
    *,
    account_id: int,
    order_source: str,
) -> list[dict[str, Any]]:
    """柜台委托对象 → paper_trade_order 行（缺 cl_ord_id 的行跳过并告警）。"""
    rows: list[dict[str, Any]] = []
    for item in _rows(raw):
        cl_ord_id = str(item.get("cl_ord_id") or "").strip()
        if not cl_ord_id:
            logger.warning("paper_trade_order_missing_cl_ord_id", raw=item)
            continue
        symbol = str(item.get("symbol") or "")
        created = _counter_datetime(item.get("created_at"))
        rows.append(
            {
                "paper_trade_account_id": account_id,
                "order_source": order_source,
                "cl_ord_id": cl_ord_id,
                "trade_date": _cn_trade_date(
                    created or _counter_datetime(item.get("updated_at")),
                    fallback_date,
                ),
                "symbol": symbol,
                "stock_code": _stock_code(symbol),
                "side": _to_int(item.get("side")) or 0,
                "order_type": _to_int(item.get("order_type")) or 0,
                "position_effect": _to_int(item.get("position_effect")) or 1,
                "price": _to_decimal(item.get("price")) or Decimal("0"),
                "volume": _to_int(item.get("volume")) or 0,
                "status": _to_int(item.get("status")) or 0,
                "ord_rej_reason": _to_int(item.get("ord_rej_reason")),
                "ord_rej_reason_detail": item.get("ord_rej_reason_detail"),
                "counter_created_at": created,
                "counter_updated_at": _counter_datetime(item.get("updated_at")),
                "raw": item,
            }
        )
    return rows


def _normalize_executions(
    raw: Any,
    fallback_date: date,
    *,
    account_id: int,
) -> list[dict[str, Any]]:
    """柜台回报对象 → paper_trade_execution 行（幂等键缺失时回退组合键）。"""
    rows: list[dict[str, Any]] = []
    for item in _rows(raw):
        exec_id = next(
            (str(item[key]).strip() for key in _EXEC_ID_KEYS if item.get(key)), ""
        )
        cl_ord_id = str(item.get("cl_ord_id") or "").strip()
        created = _counter_datetime(item.get("created_at"))
        if not exec_id:
            if not (cl_ord_id and created):
                logger.warning("paper_trade_execution_missing_exec_id", raw=item)
                continue
            exec_id = f"{cl_ord_id}:{created.isoformat()}"
        symbol = str(item.get("symbol") or "")
        price = _to_decimal(item.get("price"))
        volume = _to_int(item.get("volume"))
        turnover = _to_decimal(item.get("turnover"))
        if turnover is None and price is not None and volume:
            # 掘金回报不带成交额：按 价×量 本地补算（与股票软件口径一致）
            turnover = _q2(price * volume)
        rows.append(
            {
                "paper_trade_account_id": account_id,
                "exec_id": exec_id,
                "cl_ord_id": cl_ord_id,
                "trade_date": _cn_trade_date(created, fallback_date),
                "symbol": symbol,
                "side": _to_int(item.get("side")),
                "exec_type": _to_int(item.get("exec_type")),
                "price": price,
                "volume": volume,
                "turnover": turnover,
                "commission": _to_decimal(item.get("commission")),
                "counter_created_at": created,
                "raw": item,
            }
        )
    return rows


def _normalize_cash(raw: Any, trade_date: date) -> dict[str, Any]:
    """柜台资金概况 → paper_trade_cash_snapshot 行（一日一行，账户维度由调用方补齐）。

    柜台对单对象也包数组返回（实测 ``[ {...} ]``），取首个 dict。
    """
    if isinstance(raw, list):
        data = next((row for row in raw if isinstance(row, dict)), {})
    elif isinstance(raw, dict):
        data = raw
    else:
        data = {}
    return {
        "trade_date": trade_date,
        "nav": _to_decimal(data.get("nav")),
        "available": _to_decimal(data.get("available")),
        "balance": _to_decimal(data.get("balance")),
        "cum_inout": _to_decimal(data.get("cum_inout")),
        "last_inout": _to_decimal(data.get("last_inout")),
    }


def _order_wire_row(item: dict[str, Any], fallback_date: date) -> dict[str, Any]:
    """柜台委托对象 → wire 行（camelCase 由 schema 层出，此处 snake 键构造）。"""
    symbol = str(item.get("symbol") or "")
    created = _counter_datetime(item.get("created_at"))
    return {
        "cl_ord_id": str(item.get("cl_ord_id") or ""),
        "trade_date": _cn_trade_date(created, fallback_date),
        "symbol": symbol,
        "stock_code": _stock_code(symbol),
        "side": _to_int(item.get("side")) or 0,
        "order_type": _to_int(item.get("order_type")) or 0,
        "position_effect": _to_int(item.get("position_effect")) or 1,
        "price": _to_decimal(item.get("price")) or Decimal("0"),
        "volume": _to_int(item.get("volume")) or 0,
        "status": _to_int(item.get("status")) or 0,
        "ord_rej_reason": _to_int(item.get("ord_rej_reason")),
        "ord_rej_reason_detail": item.get("ord_rej_reason_detail"),
        "counter_created_at": created,
        "counter_updated_at": _counter_datetime(item.get("updated_at")),
    }


def _position_wire_row(item: dict[str, Any]) -> dict[str, Any]:
    """柜台持仓对象 → wire 行（字段名多候选容错，缺失项为 None）。

    柜台 float32 噪声与浮盈缺失在此收敛：价格/金额 quantize；
    profit/profit_rate 柜台未给时按 (现价-成本)×数量 本地补算（同 A 股软件口径）。
    """
    symbol = str(item.get("symbol") or "")
    volume = _to_int(_first(item, "volume", "total_volume"))
    avg_price = _q4(_to_decimal(_first(item, "price", "vwap", "avg_price", "open_price")))
    last_price = _q4(_to_decimal(_first(item, "last_price", "current_price", "close")))
    profit = _q2(_to_decimal(_first(item, "profit", "float_profit", "position_profit")))
    profit_rate = _q4(_to_decimal(_first(item, "profit_rate", "profit_ratio")))
    if profit is None and volume and avg_price is not None and last_price is not None:
        profit = _q2((last_price - avg_price) * volume)
    if profit_rate is None and profit is not None and volume and avg_price:
        profit_rate = _q4(profit / (avg_price * volume) * 100)
    return {
        "symbol": symbol,
        "stock_code": _stock_code(symbol),
        "side": _to_int(item.get("side")),
        "volume": volume,
        "available_volume": _to_int(
            _first(item, "available_volume", "avail_volume", "available")
        ),
        "avg_price": avg_price,
        "last_price": last_price,
        "market_value": _q2(_to_decimal(_first(item, "market_value", "position_value"))),
        "profit": profit,
        "profit_rate": profit_rate,
    }


def _client() -> PaperTradeClient:
    settings = get_settings()
    if not settings.paper_trade_url:
        raise PaperTradeNotConfiguredError()
    return PaperTradeClient(settings.paper_trade_url)


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
    order_rows = _normalize_orders(
        await client.get_intraday_orders(credentials),
        resolved,
        account_id=account.id,
        order_source=(
            account_service.ORDER_SOURCE_AGENT
            if account.is_agent
            else account_service.ORDER_SOURCE_MANUAL
        ),
    )
    execution_rows = _normalize_executions(
        await client.get_intraday_executions(credentials),
        resolved,
        account_id=account.id,
    )
    cash_row = _normalize_cash(await client.get_cash(credentials), resolved)
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
    client = _client()

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
            PaperTradeAccount.is_agent,
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
                "is_agent": account.is_agent,
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
    client = _client()

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


async def get_overview(session: AsyncSession, account: PaperTradeAccount) -> dict[str, Any]:
    """实时总览透传（资金 / 持仓 / 未结委托），不落库。

    持仓可用数做 T+1 修正：掘金仿真 available 把当日买入计入可卖（与 A 股
    T+1 规则不符），此处扣减本地今日已成交买入量，下限 0。

    Raises:
        PaperTradeNotConfiguredError: paper_trade_url 未配置。
        PaperTradeGatewayError: sidecar 或柜台错误。
    """
    client = _client()
    credentials = account_service.credentials_for(account)
    today = today_cn()
    cash_row = _normalize_cash(await client.get_cash(credentials), today)
    cash_wire = {
        key: float(value) if value is not None else None
        for key, value in cash_row.items()
        if key != "trade_date"
    }
    bought_today = await _bought_today_by_code(session, account.id, today)
    positions = []
    for row in _rows(await client.get_positions(credentials)):
        position = _position_wire_row(row)
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
            _order_wire_row(row, today)
            for row in _rows(await client.get_unfinished_orders(credentials))
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
    return {_stock_code(sym): int(vol or 0) for sym, vol in result.all()}


def _ensure_manual_tradable(account: PaperTradeAccount) -> None:
    """人工交易守卫：agent 专属账户与停用账户一律 403（与前端禁用态同契约）。"""
    if account.is_agent:
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
    client = _client()
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
    client = _client()
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
    if not _BARE_CODE_RE.fullmatch(code):
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
