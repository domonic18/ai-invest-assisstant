"""模拟盘复盘窗口取数与预检（generate_review 的输入侧）。

只做确定性查询：窗口内委托/成交/净值曲线组装、复盘对象判定、盘后同步
落库预检、大盘复盘语境（缺失降级 None 不阻塞）。编排与 LLM 调用见
``agent_review_service``。
"""

from datetime import date
from typing import Any

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper_trade import (
    PaperTradeCashSnapshot,
    PaperTradeExecution,
    PaperTradeOrder,
)
from app.models.stock import StockBasic
from app.services.review.market_review_service import ReviewInputDataNotReadyError


async def _stock_names(
    session: AsyncSession, codes: list[str]
) -> dict[str, str]:
    if not codes:
        return {}
    rows = await session.execute(
        select(StockBasic.stock_code, StockBasic.stock_name).where(
            StockBasic.stock_code.in_(codes)
        )
    )
    return {code: name for code, name in rows.all()}


def _serialize_dt(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


async def _collect_window_input(
    session: AsyncSession, account_id: int, start: date, end: date
) -> dict[str, Any]:
    """组装复盘输入：窗口内委托/成交（agent 账户行）+ 同区间净值曲线 + 股票名。"""
    orders = (
        (
            await session.execute(
                select(PaperTradeOrder)
                .where(
                    PaperTradeOrder.paper_trade_account_id == account_id,
                    PaperTradeOrder.trade_date.between(start, end),
                )
                .order_by(PaperTradeOrder.counter_created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    executions = (
        (
            await session.execute(
                select(PaperTradeExecution)
                .where(
                    PaperTradeExecution.paper_trade_account_id == account_id,
                    PaperTradeExecution.trade_date.between(start, end),
                )
                .order_by(PaperTradeExecution.counter_created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    nav_curve = (
        (
            await session.execute(
                select(PaperTradeCashSnapshot)
                .where(
                    PaperTradeCashSnapshot.paper_trade_account_id == account_id,
                    PaperTradeCashSnapshot.trade_date.between(start, end),
                )
                .order_by(PaperTradeCashSnapshot.trade_date.asc())
            )
        )
        .scalars()
        .all()
    )

    def _row(obj: Any, fields: list[str]) -> dict[str, Any]:
        return {
            field: _serialize_dt(getattr(obj, field))
            for field in fields
            if getattr(obj, field, None) is not None
        }

    codes = sorted({o.stock_code for o in orders} | {e.symbol.split(".")[-1] for e in executions})
    names = await _stock_names(session, codes)
    return {
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "stock_names": names,
        "orders": [
            _row(
                o,
                [
                    "cl_ord_id",
                    "trade_date",
                    "stock_code",
                    "side",
                    "order_type",
                    "price",
                    "volume",
                    "status",
                    "ord_rej_reason_detail",
                    "order_source",
                ],
            )
            for o in orders
        ],
        "executions": [
            _row(
                e,
                [
                    "exec_id",
                    "cl_ord_id",
                    "trade_date",
                    "symbol",
                    "side",
                    "price",
                    "volume",
                    "turnover",
                    "commission",
                ],
            )
            for e in executions
        ],
        "nav_curve": [
            _row(s, ["trade_date", "nav", "available", "cum_inout"]) for s in nav_curve
        ],
    }


async def _has_review_target(
    session: AsyncSession, account_id: int, start: date, end: date
) -> bool:
    """有窗口内委托/成交，或历史曾成交（即有持仓来源）→ 有复盘对象。"""
    for model in (PaperTradeOrder, PaperTradeExecution):
        stmt = select(1).where(
            model.paper_trade_account_id == account_id,  # type: ignore[attr-defined]
            model.trade_date.between(start, end),
        )
        if await session.scalar(select(exists(stmt))):
            return True
    any_exec = await session.scalar(
        select(
            exists(
                select(1).where(
                    PaperTradeExecution.paper_trade_account_id == account_id
                )
            )
        )
    )
    return bool(any_exec)


async def _sync_landed(session: AsyncSession, account_id: int, day: date) -> bool:
    """16:00 盘后同步落库标志：当日资金快照行存在（sync 无条件 upsert）。"""
    return bool(
        await session.scalar(
            select(
                exists(
                    select(1).where(
                        PaperTradeCashSnapshot.paper_trade_account_id == account_id,
                        PaperTradeCashSnapshot.trade_date == day,
                    )
                )
            )
        )
    )


async def _market_review_optional(session: AsyncSession, trade_date: date) -> dict[str, Any] | None:
    """基准交易日全市场复盘解读（D34 盘面语境输入）；缺失降级 None 不阻塞——
    常态 18:35 已就绪早于复盘 19:00，补跑历史窗口时才可能缺失。"""
    from app.services.trading.agent_plan_input import _market_review_sections

    try:
        review = await _market_review_sections(session, trade_date)
    except ReviewInputDataNotReadyError:
        return None
    return review.get("sections") or review
