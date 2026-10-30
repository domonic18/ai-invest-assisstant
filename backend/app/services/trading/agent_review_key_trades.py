"""长周期复盘的关键交易确定性筛选（§4.2：长周期不做全量逐笔）。

筛三类点评对象并打标签：盈亏前列（已实现卖出按移动加权成本排序）、
计划外单/计划区间外买入、废单拒单。标签只用于提示 LLM 点评对象与理由，
数值仍以 ``agent_review_metrics`` 聚合为准。

筛选上限：每类 Top N + 总数上限，保证输入规模不随交易笔数线性膨胀；
被筛掉的成交仍计入 metrics 聚合，不丢失统计口径。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper_trade import PaperTradeOrder
from app.services.trading.agent_review_metrics import (
    PLAN_SIDE,
    ExecutionRecord,
    PlanRecord,
    RealizedTrade,
    load_executions,
    load_plans,
    realized_trades,
)
from app.services.trading.agent_review_periods import ReviewWindow
from app.services.trading.paper_trade_converters import (
    ORDER_STATUS_REJECTED,
    SIDE_BUY,
    bare_stock_code,
)

#: 每类关键交易条数上限（盈利/亏损/计划外/区间外/废单拒单各自）
KEY_TRADE_TOP_N = 3

#: 关键交易总数上限 = 五类各自上限之和（控输入规模，且不淘汰任何整类）
KEY_TRADE_MAX = KEY_TRADE_TOP_N * 5

TAG_WINNER = "盈利前列"
TAG_LOSER = "亏损前列"
TAG_OFF_PLAN = "计划外单"
TAG_OUT_OF_ZONE = "计划区间外"
TAG_REJECTED = "废单拒单"


@dataclass(frozen=True)
class KeyTradeSelection:
    """关键交易筛选结果：保留的委托 id（按优先级去重）+ 每笔标签。"""

    cl_ord_ids: tuple[str, ...]
    tags: dict[str, tuple[str, ...]]
    total_candidates: int

    def to_wire(self) -> dict[str, Any]:
        """注入 LLM 输入的形状（列表而非元组，便于 JSON 序列化）。"""
        return {
            "cl_ord_ids": list(self.cl_ord_ids),
            "tags": {key: list(value) for key, value in self.tags.items()},
            "total_candidates": self.total_candidates,
            "note": (
                f"输入已筛为关键交易（共 {len(self.cl_ord_ids)} 笔，候选 "
                f"{self.total_candidates} 笔）：其余成交只计入 metrics 聚合，"
                "不代表全部交易"
            ),
        }


def _dedupe(cl_ord_ids: Sequence[str]) -> list[str]:
    """保序去重（限量前先合并重复委托 id，避免名额被占）。"""
    return list(dict.fromkeys(cl_ord_ids))


def _plan_index(
    plans: Sequence[PlanRecord],
) -> dict[tuple[date, str, int | None], PlanRecord]:
    return {
        (plan.plan_date, plan.stock_code, PLAN_SIDE.get(plan.plan_type)): plan
        for plan in plans
        if plan.plan_type in PLAN_SIDE
    }


def _deviation_tag(
    execution: ExecutionRecord,
    index: dict[tuple[date, str, int | None], PlanRecord],
) -> str | None:
    """单笔成交的偏离标签：无当日同方向计划 → 计划外；买入价出区间 → 区间外。"""
    plan = index.get((execution.trade_date, execution.stock_code, execution.side))
    if plan is None:
        return TAG_OFF_PLAN
    if (
        execution.side == SIDE_BUY
        and execution.price is not None
        and plan.buy_zone_low is not None
        and plan.buy_zone_high is not None
        and not (plan.buy_zone_low <= execution.price <= plan.buy_zone_high)
    ):
        return TAG_OUT_OF_ZONE
    return None


def select_key_trades(
    *,
    executions: Sequence[ExecutionRecord],
    plans: Sequence[PlanRecord],
    realized: Sequence[RealizedTrade],
    rejected_cl_ord_ids: Sequence[str] = (),
) -> KeyTradeSelection:
    """确定性筛选关键交易（纯函数）。

    五类各自限量（``KEY_TRADE_TOP_N``）后按优先级合并：盈利前列 → 亏损前列
    → 计划外单 → 计划区间外 → 废单拒单。逐类限量保证废单（需求 §4.2 必点评
    对象）不会被其他类别挤出；``KEY_TRADE_MAX`` 是所有类别上限之和，仅作
    输入规模兜底。同笔多标签合并保留。
    """
    tags: dict[str, list[str]] = {}
    order: list[str] = []

    def add(cl_ord_id: str | None, tag: str) -> None:
        if not cl_ord_id:
            return
        if cl_ord_id not in tags:
            tags[cl_ord_id] = []
            order.append(cl_ord_id)
        if tag not in tags[cl_ord_id]:
            tags[cl_ord_id].append(tag)

    sellers = [trade for trade in realized if trade.cl_ord_id]
    winners = sorted(
        (trade for trade in sellers if trade.profit > 0),
        key=lambda trade: trade.profit,
        reverse=True,
    )
    losers = sorted(
        (trade for trade in sellers if trade.profit < 0),
        key=lambda trade: trade.profit,
    )
    for trade in winners[:KEY_TRADE_TOP_N]:
        add(trade.cl_ord_id, TAG_WINNER)
    for trade in losers[:KEY_TRADE_TOP_N]:
        add(trade.cl_ord_id, TAG_LOSER)

    index = _plan_index(plans)
    off_plan: list[str] = []
    out_of_zone: list[str] = []
    for execution in executions:
        tag = _deviation_tag(execution, index)
        if execution.cl_ord_id is None:
            continue
        if tag == TAG_OFF_PLAN:
            off_plan.append(execution.cl_ord_id)
        elif tag == TAG_OUT_OF_ZONE:
            out_of_zone.append(execution.cl_ord_id)
    unique_off_plan = _dedupe(off_plan)
    unique_out_of_zone = _dedupe(out_of_zone)
    unique_rejected = _dedupe(rejected_cl_ord_ids)
    for cl_ord_id in unique_off_plan[:KEY_TRADE_TOP_N]:
        add(cl_ord_id, TAG_OFF_PLAN)
    for cl_ord_id in unique_out_of_zone[:KEY_TRADE_TOP_N]:
        add(cl_ord_id, TAG_OUT_OF_ZONE)
    for cl_ord_id in unique_rejected[:KEY_TRADE_TOP_N]:
        add(cl_ord_id, TAG_REJECTED)

    # 候选数按限量前的全部合格委托计（限量后被丢弃的条数对 LLM 可见）
    ranked = [trade.cl_ord_id for trade in (*winners, *losers)]
    candidates = _dedupe(
        [
            cl_ord_id
            for cl_ord_id in (
                *ranked,
                *unique_off_plan,
                *unique_out_of_zone,
                *unique_rejected,
            )
            if cl_ord_id
        ]
    )

    kept = order[:KEY_TRADE_MAX]
    return KeyTradeSelection(
        cl_ord_ids=tuple(kept),
        tags={cl_ord_id: tuple(tags[cl_ord_id]) for cl_ord_id in kept},
        total_candidates=len(candidates),
    )


def filter_window_input(
    window_input: dict[str, Any], selection: KeyTradeSelection
) -> dict[str, Any]:
    """把复盘输入裁剪到关键交易，并附标签与说明（原地不修改入参）。"""
    kept = set(selection.cl_ord_ids)
    orders = [
        order
        for order in window_input.get("orders", [])
        if order.get("cl_ord_id") in kept
    ]
    executions = [
        execution
        for execution in window_input.get("executions", [])
        if execution.get("cl_ord_id") in kept
    ]
    codes = {order.get("stock_code") for order in orders}
    codes |= {
        bare_stock_code(str(execution.get("symbol") or ""))
        for execution in executions
    }
    names = {
        code: name
        for code, name in (window_input.get("stock_names") or {}).items()
        if code in codes
    }
    return {
        **window_input,
        "orders": orders,
        "executions": executions,
        "stock_names": names,
        "key_trades": selection.to_wire(),
    }


async def _load_rejected_orders(
    session: AsyncSession, account_id: int, start: date, end: date
) -> list[str]:
    rows = (
        await session.execute(
            select(PaperTradeOrder.cl_ord_id).where(
                PaperTradeOrder.paper_trade_account_id == account_id,
                PaperTradeOrder.trade_date.between(start, end),
                PaperTradeOrder.status == ORDER_STATUS_REJECTED,
            )
        )
    ).all()
    return [str(cl_ord_id) for (cl_ord_id,) in rows if cl_ord_id]


async def load_key_trade_selection(
    session: AsyncSession,
    *,
    account_id: int,
    agent_key: str,
    window: ReviewWindow,
) -> KeyTradeSelection:
    """取数并筛选窗口关键交易（只读）。"""
    executions = await load_executions(session, account_id, window.end)
    plans = await load_plans(session, agent_key, window.start, window.end)
    realized = realized_trades(executions, start=window.start, end=window.end)
    rejected = await _load_rejected_orders(
        session, account_id, window.start, window.end
    )
    in_window = [
        execution
        for execution in executions
        if window.start <= execution.trade_date <= window.end
    ]
    return select_key_trades(
        executions=in_window,
        plans=plans,
        realized=realized,
        rejected_cl_ord_ids=rejected,
    )
