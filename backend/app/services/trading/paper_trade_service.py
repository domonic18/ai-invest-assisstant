"""模拟盘盘后同步与本地查询服务。

16:00 盘后（或手动）拉取掘金仿真当日委托/成交回报/资金概况，幂等 upsert 三表：
委托按 cl_ord_id 冲突更新状态，回报按 exec_id 冲突跳过（不可变），资金按
trade_date 冲突覆盖。``redis_lock`` 防并发；写操作显式 commit。
本模块顶层只依赖 sidecar client 与 models，禁止导入 agent/skills/runtime。
"""

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import CN_TZ, utc_now
from app.core.config import get_settings
from app.core.exceptions import ConflictError
from app.core.locking import DEFAULT_LOCK_TTL_SECONDS, redis_lock
from app.models.paper_trade import (
    PaperTradeCashSnapshot,
    PaperTradeExecution,
    PaperTradeOrder,
)
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


def _normalize_orders(raw: Any, fallback_date: date) -> list[dict[str, Any]]:
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


def _normalize_executions(raw: Any, fallback_date: date) -> list[dict[str, Any]]:
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
        rows.append(
            {
                "exec_id": exec_id,
                "cl_ord_id": cl_ord_id,
                "trade_date": _cn_trade_date(created, fallback_date),
                "symbol": symbol,
                "side": _to_int(item.get("side")),
                "exec_type": _to_int(item.get("exec_type")),
                "price": _to_decimal(item.get("price")),
                "volume": _to_int(item.get("volume")),
                "turnover": _to_decimal(item.get("turnover")),
                "commission": _to_decimal(item.get("commission")),
                "counter_created_at": created,
                "raw": item,
            }
        )
    return rows


def _normalize_cash(raw: Any, trade_date: date) -> dict[str, Any]:
    """柜台资金概况 → paper_trade_cash_snapshot 行（一日一行）。

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


async def _upsert_orders(session: AsyncSession, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    stmt = pg_insert(PaperTradeOrder).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[PaperTradeOrder.cl_ord_id],
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
    stmt = stmt.on_conflict_do_nothing(index_elements=[PaperTradeExecution.exec_id])
    await session.execute(stmt)
    return len(rows)


async def _upsert_cash(session: AsyncSession, row: dict[str, Any]) -> None:
    stmt = pg_insert(PaperTradeCashSnapshot).values([row])
    stmt = stmt.on_conflict_do_update(
        index_elements=[PaperTradeCashSnapshot.trade_date],
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


async def sync_daily(
    session: AsyncSession, trade_date: date | None = None
) -> dict[str, Any]:
    """拉取掘金仿真当日委托/成交/资金，幂等 upsert 三表。

    Args:
        session: 数据库会话（写操作显式 commit）。
        trade_date: 业务日；缺省取最近交易日（周末手动补跑不落空）。

    Returns:
        同步摘要 {trade_date, orders, executions, nav}。

    Raises:
        PaperTradeNotConfiguredError: paper_trade_url 未配置。
        ConflictError: 其他实例正在同步。
        PaperTradeGatewayError: sidecar 或柜台错误。
    """
    settings = get_settings()
    if not settings.paper_trade_url:
        raise PaperTradeNotConfiguredError()

    # 延迟 import：market 子域聚合面大，避免顶层环导入
    from app.services.market import trade_calendar_service

    resolved = trade_date or await trade_calendar_service.resolve_latest_trade_date(
        session
    )

    async with redis_lock(SYNC_LOCK_KEY, ttl=DEFAULT_LOCK_TTL_SECONDS) as acquired:
        if not acquired:
            raise ConflictError("模拟盘盘后同步正在执行，请稍后重试")
        client = PaperTradeClient(settings.paper_trade_url)
        order_rows = _normalize_orders(await client.get_intraday_orders(), resolved)
        execution_rows = _normalize_executions(
            await client.get_intraday_executions(), resolved
        )
        cash_row = _normalize_cash(await client.get_cash(), resolved)

        stored_orders = await _upsert_orders(session, order_rows)
        stored_executions = await _insert_executions(session, execution_rows)
        await _upsert_cash(session, cash_row)
        await session.commit()

    summary = {
        "trade_date": resolved.isoformat(),
        "orders": stored_orders,
        "executions": stored_executions,
        # float 而非 Decimal：summary 会进 collector_log.metadata（JSONB），Decimal 不可序列化
        "nav": float(cash_row["nav"]) if cash_row["nav"] is not None else None,
    }
    logger.info("paper_trade_synced", **summary)
    return summary


async def get_orders(
    session: AsyncSession, trade_date: date
) -> list[PaperTradeOrder]:
    """按业务日查本地委托（id 升序 = 落库顺序）。"""
    result = await session.execute(
        select(PaperTradeOrder)
        .where(PaperTradeOrder.trade_date == trade_date)
        .order_by(PaperTradeOrder.id)
    )
    return list(result.scalars().all())


async def get_executions(
    session: AsyncSession, trade_date: date
) -> list[PaperTradeExecution]:
    """按业务日查本地成交回报。"""
    result = await session.execute(
        select(PaperTradeExecution)
        .where(PaperTradeExecution.trade_date == trade_date)
        .order_by(PaperTradeExecution.id)
    )
    return list(result.scalars().all())


async def get_nav_history(
    session: AsyncSession, days: int = 30
) -> list[PaperTradeCashSnapshot]:
    """最近 N 个交易日的资金快照（按 trade_date 升序返回）。"""
    result = await session.execute(
        select(PaperTradeCashSnapshot)
        .order_by(PaperTradeCashSnapshot.trade_date.desc())
        .limit(days)
    )
    return list(reversed(result.scalars().all()))
