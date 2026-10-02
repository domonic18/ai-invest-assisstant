"""盘中计划校准服务（§11.5，D22）：慢模型读观察报告对当日计划出修正单。

早盘 10:20 / 午盘 13:20（Celery → internal 采集器 → 本服务，heavy 队列）。
快→慢输入为 ``paper_trade_exec_observation`` 当日聚合（执行概率轨迹 /
抑制清单 / 最新价）；慢→快输出为结构化修正单（maintain/adjust/cancel/add），
逐条落 ``agent_trade_plan_amendment`` 留痕。

边界（方案定版）：
- 校准不是风控旁路：修正单必须过确定性硬校验（区间自洽 + 死单体检 +
  单票仓位上限 + 标的存在性），被拒修正单留痕不生效；
- ``calibration_mode='shadow'`` 只留痕不改计划（影子期先行），'active' 才
  生效——adjust 推计划 ``version`` 自增，tick 无状态重读自然感知；
- 盘中一次性语义不缓存（区别于盘后链的缓存优先）；同窗口幂等靠
  执行前已存在检查 + (agent, date, window, stock_code) 唯一约束。
"""

import json
from datetime import date
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, UnprocessableEntityError
from app.core.locking import GENERATION_LOCK_TTL_SECONDS, redis_lock
from app.models.agent_trading import AgentTradePlan, AgentTradePlanAmendment
from app.models.paper_trade import PaperTradeExecObservation, TradingAgent
from app.models.stock import StockBasic
from app.services.trading import agent_intraday_decision
from app.services.trading.agent_plan_schemas import (
    PlanCalibrationContent,
    PlanCalibrationItem,
)
from app.services.trading.agent_plan_service import plan_skill_id
from app.skills import load_named_skill_prompt

logger = structlog.get_logger(__name__)

WINDOW_MORNING = "1020"
WINDOW_AFTERNOON = "1320"
WINDOW_LABELS = {"1020": "早盘校准", "1320": "午盘校准"}


class CalibrationLockedError(ConflictError):
    """其他实例正在执行同窗口校准。"""

    default_message = "计划校准正在执行中，请稍后重试"


def _f(value: Any) -> float | None:
    """Decimal/None → JSON 友好 float。"""
    return float(value) if value is not None else None


def _d(value: float | None) -> Decimal | None:
    """LLM 输出 float → Numeric 列 Decimal。"""
    return Decimal(str(value)) if value is not None else None


async def build_observation_report(
    session: AsyncSession, agent_key: str, trade_date: date
) -> list[dict[str, Any]]:
    """快→慢「盘中观察报告」：当日观测按标的聚合（§11.5 契约输入形状）。

    逐标的给出 tick 数、动作/抑制/判定分布与最新价——执行概率轨迹的
    紧凑投影，供慢模型直读。
    """
    rows = (
        await session.scalars(
            select(PaperTradeExecObservation)
            .where(
                PaperTradeExecObservation.agent_key == agent_key,
                PaperTradeExecObservation.trade_date == trade_date,
            )
            .order_by(PaperTradeExecObservation.tick_time)
        )
    ).all()
    report: dict[str, dict[str, Any]] = {}
    for row in rows:
        entry = report.setdefault(
            row.stock_code,
            {
                "stock_code": row.stock_code,
                "plan_id": row.plan_id,
                "ticks": 0,
                "actions": {},
                "suppressed": {},
                "verdicts": {},
                "last_price": None,
                "last_change_pct": None,
            },
        )
        entry["ticks"] += 1
        entry["plan_id"] = row.plan_id or entry["plan_id"]
        if row.action:
            entry["actions"][row.action] = entry["actions"].get(row.action, 0) + 1
        if row.suppression_reason:
            entry["suppressed"][row.suppression_reason] = (
                entry["suppressed"].get(row.suppression_reason, 0) + 1
            )
        entry["verdicts"][row.l0_verdict] = entry["verdicts"].get(row.l0_verdict, 0) + 1
        snapshot = row.market_snapshot or {}
        if snapshot.get("price") is not None:
            entry["last_price"] = snapshot["price"]
            entry["last_change_pct"] = snapshot.get("change_pct")
    return list(report.values())


async def run_calibration(
    session: AsyncSession,
    agent: TradingAgent,
    trade_date: date,
    window: str,
    *,
    quotes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """执行一次校准窗口：观察报告 → 慢模型修正单 → 硬校验 → 留痕/生效。

    Args:
        session: 数据库会话（服务层拥有事务边界，成功后 commit）。
        agent: 注册行（calibration_mode 决定生效路径）。
        trade_date: 基准交易日（只对当日 active 计划表态）。
        window: 校准窗口 ``1020``/``1320``。
        quotes: 计划标的实时行情（``fetch_sina_quotes`` 形状，采集器预取）。

    Returns:
        计数摘要（total/maintain/adjust/cancel/add/applied/shadow/rejected
        /new_plan_ids）；``cached=True`` 表示该窗口已校准（幂等跳过）；
        ``skipped_reason`` 非空表示无表态对象。

    Raises:
        CalibrationLockedError: 其他实例正在执行同窗口校准。
        UnprocessableEntityError: window 非法。
    """
    if window not in WINDOW_LABELS:
        raise UnprocessableEntityError(f"非法校准窗口 {window}（仅限 1020/1320）")

    lock_key = f"agent-plan-calib:{agent.agent_key}:{trade_date.isoformat()}:{window}"
    async with redis_lock(lock_key, ttl=GENERATION_LOCK_TTL_SECONDS, blocking=False) as acquired:
        if not acquired:
            raise CalibrationLockedError()
        return await _run_locked(session, agent, trade_date, window, quotes=quotes)


async def _run_locked(
    session: AsyncSession,
    agent: TradingAgent,
    trade_date: date,
    window: str,
    *,
    quotes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    existing = await session.scalar(
        select(func.count())
        .select_from(AgentTradePlanAmendment)
        .where(
            AgentTradePlanAmendment.agent_key == agent.agent_key,
            AgentTradePlanAmendment.plan_date == trade_date,
            AgentTradePlanAmendment.window == window,
        )
    )
    if existing:
        return {"cached": True, "window": window, "total": 0}

    plans = list(
        (
            await session.scalars(
                select(AgentTradePlan)
                .where(
                    AgentTradePlan.agent_key == agent.agent_key,
                    AgentTradePlan.plan_date == trade_date,
                    AgentTradePlan.status == "active",
                )
                .order_by(AgentTradePlan.id)
            )
        ).all()
    )
    if not plans:
        return {
            "cached": False,
            "window": window,
            "total": 0,
            "skipped_reason": "无当日活跃计划",
        }

    report = await build_observation_report(session, agent.agent_key, trade_date)
    meta_out: dict[str, Any] = {}
    content = await _run_llm(
        session, agent, trade_date, window, plans, report, quotes, meta_out=meta_out
    )
    summary = await _apply_amendments(
        session, agent, trade_date, window, content, quotes, plans,
        model_name=meta_out.get("model_name"),
    )
    await session.commit()
    logger.info(
        "plan_calibration_done",
        agent_key=agent.agent_key,
        trade_date=trade_date.isoformat(),
        window=window,
        total=summary["total"],
        applied=summary["applied"],
        shadow=summary["shadow"],
        rejected=summary["rejected"],
    )
    return summary


async def _run_llm(
    session: AsyncSession,
    agent: TradingAgent,
    trade_date: date,
    window: str,
    plans: list[AgentTradePlan],
    report: list[dict[str, Any]],
    quotes: dict[str, dict[str, Any]],
    *,
    meta_out: dict[str, Any],
) -> PlanCalibrationContent:
    """组装校准提示词并执行结构化调用（无缓存，盘中一次性语义）。"""
    config = load_named_skill_prompt(plan_skill_id(agent.agent_key), "calibration_prompt.yaml")
    identity = f"- 你是{agent.name}" + (f"（{agent.tagline}）" if agent.tagline else "")
    plans_json = [
        {
            "plan_id": p.id,
            "stock_code": p.stock_code,
            "plan_type": p.plan_type,
            "strategy": p.strategy,
            "buy_zone_low": _f(p.buy_zone_low),
            "buy_zone_high": _f(p.buy_zone_high),
            "target_price": _f(p.target_price),
            "stop_loss": _f(p.stop_loss),
            "position_pct": _f(p.position_pct),
            "version": p.version,
        }
        for p in plans
    ]
    quotes_json = [
        {"stock_code": p.stock_code, **quotes[p.stock_code]}
        for p in plans
        if p.stock_code in quotes
    ]
    user_prompt = (
        f"{config.system_prompt}\n\n"
        f"## 计划人设（注册表行）\n{identity}\n- 以该人设的视角与风格校准当日交易计划\n\n"
        f"## 校准任务\n"
        f"- 基准交易日 trade_date：{trade_date.isoformat()}（输出字段须原样带回）\n"
        f"- 校准窗口：{WINDOW_LABELS[window]}（window={window}）\n"
        f"- 只对上列当日计划逐条表态；计划外强机会才允许 add\n\n"
        f"## 当日计划（JSON）\n{json.dumps(plans_json, ensure_ascii=False, default=str)}\n\n"
        f"## 当前行情（JSON，仅计划标的）\n{json.dumps(quotes_json, ensure_ascii=False)}\n\n"
        f"## 盘中观察报告（JSON，快反应逐 tick 判定聚合）\n"
        f"{json.dumps(report, ensure_ascii=False, default=str)}\n"
    )
    from app.agent.runtime.structured import run_structured

    return await run_structured(
        session,
        result_type=PlanCalibrationContent,
        user_prompt=user_prompt,
        config_id=agent.llm_config_id,
        meta_out=meta_out,
    )


def _merged(plan: AgentTradePlan, item: PlanCalibrationItem) -> dict[str, Any]:
    """adjust 生效后的价位形状：新值非 None 取新值，否则回落原计划值。"""
    return {
        "buy_zone_low": _d(item.new_buy_zone_low)
        if item.new_buy_zone_low is not None
        else plan.buy_zone_low,
        "buy_zone_high": _d(item.new_buy_zone_high)
        if item.new_buy_zone_high is not None
        else plan.buy_zone_high,
        "target_price": _d(item.new_target_price)
        if item.new_target_price is not None
        else plan.target_price,
        "stop_loss": _d(item.new_stop_loss)
        if item.new_stop_loss is not None
        else plan.stop_loss,
    }


def _validate_adjust(
    plan: AgentTradePlan, item: PlanCalibrationItem, price: float | None
) -> str | None:
    """adjust 硬校验：至少一项新值 + 区间自洽 + 修正后过死单体检。"""
    carries_new = any(
        v is not None
        for v in (
            item.new_buy_zone_low,
            item.new_buy_zone_high,
            item.new_target_price,
            item.new_stop_loss,
        )
    )
    if not carries_new:
        return "adjust 未携带任何新价位"
    merged = _merged(plan, item)
    if plan.plan_type == "sell":
        target = merged["target_price"]
        stop = merged["stop_loss"]
        if target is not None and stop is not None and target <= stop:
            return "sell 止盈不高于止损"
        return None
    low = merged["buy_zone_low"]
    high = merged["buy_zone_high"]
    stop = merged["stop_loss"]
    if low is None or high is None:
        return "buy 计划缺买点区间"
    if low > high:
        return "买点区间倒挂"
    if stop >= low:
        return "止损不低于买点区间下沿"
    if price is not None:
        reason = agent_intraday_decision.plan_sanity_reason(
            plan_type="buy", buy_zone_high=high, stop_loss=stop, price=price
        )
        if reason is not None:
            return f"修正后仍无法通过死单体检：{reason}"
    return None


async def _validate_add(
    session: AsyncSession,
    agent: TradingAgent,
    item: PlanCalibrationItem,
    price: float | None,
) -> str | None:
    """add 硬校验：字段完备 + 区间自洽 + 仓位上限 + 标的存在 + 死单体检。"""
    if item.plan_type is None:
        return "add 缺 plan_type"
    stop = _d(item.new_stop_loss)
    position_pct = _d(item.new_position_pct)
    if stop is None:
        return "add 缺止损"
    if position_pct is None:
        return "add 缺仓位"
    if item.plan_type == "buy":
        low = _d(item.new_buy_zone_low)
        high = _d(item.new_buy_zone_high)
        if low is None or high is None:
            return "buy 计划缺买点区间"
        if low > high:
            return "买点区间倒挂"
        if stop >= low:
            return "止损不低于买点区间下沿"
        if price is not None:
            reason = agent_intraday_decision.plan_sanity_reason(
                plan_type="buy", buy_zone_high=high, stop_loss=stop, price=price
            )
            if reason is not None:
                return f"新增计划无法通过死单体检：{reason}"
    else:
        target = _d(item.new_target_price)
        if target is not None and target <= stop:
            return "sell 止盈不高于止损"
    if position_pct > agent.risk_max_position_pct:
        return f"仓位 {position_pct}% 超单票上限 {agent.risk_max_position_pct}%"
    exists = await session.scalar(
        select(StockBasic.stock_code).where(StockBasic.stock_code == item.stock_code)
    )
    if exists is None:
        return "未知标的代码"
    return None


def _amendment_row(
    agent: TradingAgent,
    trade_date: date,
    window: str,
    item: PlanCalibrationItem,
    *,
    plan_id: int | None,
    status: str,
    reject_reason: str | None = None,
    new_plan_id: int | None = None,
    model_name: str | None = None,
) -> AgentTradePlanAmendment:
    return AgentTradePlanAmendment(
        agent_key=agent.agent_key,
        plan_date=trade_date,
        window=window,
        stock_code=item.stock_code,
        plan_id=plan_id,
        action=item.action,
        reason=item.reason,
        new_buy_zone_low=_d(item.new_buy_zone_low),
        new_buy_zone_high=_d(item.new_buy_zone_high),
        new_target_price=_d(item.new_target_price),
        new_stop_loss=_d(item.new_stop_loss),
        new_position_pct=_d(item.new_position_pct),
        status=status,
        reject_reason=reject_reason,
        new_plan_id=new_plan_id,
        model_name=model_name,
        raw={**item.model_dump(), "window": window},
    )


async def _apply_amendments(
    session: AsyncSession,
    agent: TradingAgent,
    trade_date: date,
    window: str,
    content: PlanCalibrationContent,
    quotes: dict[str, dict[str, Any]],
    plans: list[AgentTradePlan],
    *,
    model_name: str | None,
) -> dict[str, Any]:
    """逐条硬校验 + 按 calibration_mode 生效；全量留痕（含被拒修正单）。"""
    active = agent.calibration_mode == "active"
    plans_by_code: dict[str, AgentTradePlan] = {}
    for p in plans:
        # 同代码 buy/sell 并存时修正单锚定 buy（开仓计划是校准主对象）
        if p.stock_code not in plans_by_code or p.plan_type == "buy":
            plans_by_code[p.stock_code] = p

    counters: dict[str, Any] = {
        "window": window,
        "cached": False,
        "total": len(content.amendments),
        "maintain": 0,
        "adjust": 0,
        "cancel": 0,
        "add": 0,
        "applied": 0,
        "shadow": 0,
        "rejected": 0,
        "new_plan_ids": [],
    }
    seen_codes: set[str] = set()
    for item in content.amendments:
        counters[item.action] += 1
        plan = plans_by_code.get(item.stock_code)
        quote = quotes.get(item.stock_code) or {}
        price = float(quote["price"]) if quote.get("price") else None

        reject: str | None = None
        if item.stock_code in seen_codes:
            reject = "同一窗口重复表态"
        elif item.action == "add":
            reject = await _validate_add(session, agent, item, price)
        elif plan is None:
            reject = "未找到当日活跃计划"
        elif item.action == "adjust":
            reject = _validate_adjust(plan, item, price)
        # maintain / cancel 无需价位校验
        seen_codes.add(item.stock_code)

        if reject is not None:
            counters["rejected"] += 1
            session.add(
                _amendment_row(
                    agent, trade_date, window, item,
                    plan_id=plan.id if plan is not None else None,
                    status="rejected", reject_reason=reject, model_name=model_name,
                )
            )
            continue

        if not active:
            counters["shadow"] += 1
            session.add(
                _amendment_row(
                    agent, trade_date, window, item,
                    plan_id=plan.id if plan is not None else None,
                    status="shadow", model_name=model_name,
                )
            )
            continue

        new_plan_id: int | None = None
        if item.action == "adjust" and plan is not None:
            if item.new_buy_zone_low is not None:
                plan.buy_zone_low = _d(item.new_buy_zone_low)
            if item.new_buy_zone_high is not None:
                plan.buy_zone_high = _d(item.new_buy_zone_high)
            if item.new_target_price is not None:
                plan.target_price = Decimal(str(item.new_target_price))
            if item.new_stop_loss is not None:
                plan.stop_loss = Decimal(str(item.new_stop_loss))
            if item.new_position_pct is not None:
                plan.position_pct = Decimal(str(item.new_position_pct))
            plan.version = (plan.version or 1) + 1
        elif item.action == "cancel" and plan is not None:
            plan.status = "cancelled"
        elif item.action == "add":
            new_plan = AgentTradePlan(
                agent_key=agent.agent_key,
                plan_date=trade_date,
                stock_code=item.stock_code,
                plan_type=item.plan_type or "buy",
                strategy=(item.strategy or item.reason)[:200],
                buy_zone_low=_d(item.new_buy_zone_low),
                buy_zone_high=_d(item.new_buy_zone_high),
                target_price=_d(item.new_target_price),
                stop_loss=_d(item.new_stop_loss) or Decimal("0"),
                position_pct=_d(item.new_position_pct) or Decimal("0"),
                status="active",
                basis=f"盘中{WINDOW_LABELS[window]}新增：{item.reason}",
            )
            session.add(new_plan)
            await session.flush()
            new_plan_id = new_plan.id
            counters["new_plan_ids"].append(new_plan_id)

        counters["applied"] += 1
        session.add(
            _amendment_row(
                agent, trade_date, window, item,
                plan_id=plan.id if plan is not None else None,
                status="applied", new_plan_id=new_plan_id, model_name=model_name,
            )
        )
    return counters
