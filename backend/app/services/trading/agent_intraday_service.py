"""盘中自主执行链核心服务（批次 8 PR-1，paper-trading-plan §11 / D21/D24）。

四层栈：L0 确定性判定（精确比价 + 涨跌停粗校，纯函数）→ L1 判断模型
（一次 ask_decision 批量提问全部触发计划，Choice/Noul/Score）→ L2 阈值
抑制留痕 → L3 落 ``paper_trade_exec_observation`` 观测行。

``intraday_exec_mode`` 三态语义：``shadow`` 全链路判断留痕不下单（影子期
校准数据集）；``active`` 触发即经 ``execute_agent_order`` 真实下单并推进
计划状态机；``off`` 不进入本服务。判断模型异常为 advisory 降级：当次 tick
纯 L0，观测记 ``model_degraded``，禁止用阈值近似替代判断。
"""

from contextlib import nullcontext
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import structlog
from sqlalchemy import func, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import today_cn, utc_now
from app.core.decision_model.contracts import (
    DEFAULT_THRESHOLDS,
    DecisionThresholds,
    JudgeAnswer,
    JudgeQuestion,
    thresholds_from_extra,
)
from app.core.decision_model.errors import DecisionModelError
from app.models.agent_trading import AgentTradePlan
from app.models.llm_config import LLMConfig
from app.models.paper_trade import PaperTradeAccount, PaperTradeExecObservation, TradingAgent
from app.services.admin.decision_model_service import ask_decision
from app.services.admin.llm_config_service import LLMConfigNotConfiguredError
from app.services.trading import account_service, agent_registry
from app.services.trading.agent_intraday_questions import (
    CHOICE_ACTION_ABANDON,
    CHOICE_ACTION_EXECUTE,
    CHOICE_INTRADAY_ACTION_BUY,
    CHOICE_INTRADAY_ACTION_SELL,
    NOUL_BUY_TIMING,
    NOUL_EXIT_TIMING,
    SCORE_MARKET_SUPPORT,
)
from app.services.trading.agent_run_recorder import AgentRunRecorder
from app.services.trading.agent_trade_service import (
    RiskRejectedError,
    execute_agent_order,
)
from app.services.trading.errors import (
    AgentAccountNotDesignatedError,
    PaperTradeGatewayError,
    PaperTradeNotConfiguredError,
)
from app.services.trading.risk_control import limit_prices, price_limit_pct

logger = structlog.get_logger(__name__)

# L0 判定结论（paper_trade_exec_observation.l0_verdict 值域）
L0_NO_ACTION = "no_action"
L0_NEAR_TRIGGER = "near_trigger"
L0_TRIGGERED = "triggered"
L0_DEGRADED = "degraded"

# 触发原因 / 动作 / 抑制原因（observation 对应列值域）
REASON_BUY_ZONE = "buy_zone"
REASON_TARGET = "target"
REASON_STOP_LOSS = "stop_loss"

ACTION_EXECUTE = "execute"
ACTION_WAIT = "wait"
ACTION_ABANDON = "abandon"
ACTION_SUPPRESS = "suppress"

SUPPRESS_SHADOW = "shadow_mode"
SUPPRESS_BELOW_THRESHOLD = "below_threshold"
SUPPRESS_L0_REJECT = "l0_reject"
SUPPRESS_MODEL_DEGRADED = "model_degraded"
SUPPRESS_RISK_REJECTED = "risk_rejected"
SUPPRESS_NO_ACCOUNT = "no_account"
SUPPRESS_ORDER_ERROR = "order_error"


@dataclass(slots=True)
class L0Result:
    """L0 确定性判定结果（纯函数产物，无 IO）。"""

    verdict: str
    trigger_reason: str | None = None
    #: 纪律性否决（如已跌破止损位仍处买入计划）——非触发也非等待
    reject: bool = False
    detail: str | None = None


def evaluate_l0(
    plan: AgentTradePlan,
    *,
    price: float,
    prev_close: float | None,
    stock_name: str | None = None,
) -> L0Result:
    """单计划 L0 比价判定：buy 看买点区间，sell 看止盈/止损。

    涨跌停粗校：触发价触板时按不可成交处理（涨停不追买），以昨收推算
    （``risk_control.limit_prices``，ST ±5 依赖名称识别）；缺昨收跳过该校。
    """
    if plan.plan_type == "buy":
        if price <= float(plan.stop_loss):
            return L0Result(
                L0_NO_ACTION, reject=True, detail=f"现价 {price} 已跌破止损位 {plan.stop_loss}"
            )
        low = float(plan.buy_zone_low) if plan.buy_zone_low is not None else None
        high = float(plan.buy_zone_high) if plan.buy_zone_high is not None else None
        if low is None or high is None:
            return L0Result(L0_NO_ACTION, reject=True, detail="计划缺买点区间")
        if low <= price <= high:
            limit_up = (
                limit_prices(prev_close, price_limit_pct(stock_name, plan.stock_code))[1]
                if prev_close
                else None
            )
            if limit_up is not None and price >= limit_up:
                return L0Result(L0_NO_ACTION, detail="触板涨停，不追买")
            return L0Result(L0_TRIGGERED, REASON_BUY_ZONE)
        if price > high:
            return L0Result(L0_NO_ACTION, detail="高于买点区间，不追高")
        return L0Result(L0_NEAR_TRIGGER, detail="低于买点区间，等待回踩")

    target = float(plan.target_price) if plan.target_price is not None else None
    if target is not None and price >= target:
        return L0Result(L0_TRIGGERED, REASON_TARGET)
    if price <= float(plan.stop_loss):
        return L0Result(L0_TRIGGERED, REASON_STOP_LOSS)
    return L0Result(L0_NO_ACTION, detail="未触达止盈/止损价")


# L0 触发原因 → state 计划上下文的人话标签（供判断模型直读）
_TRIGGER_LABELS = {
    REASON_BUY_ZONE: "进入买点区间",
    REASON_TARGET: "触及止盈目标",
    REASON_STOP_LOSS: "击穿止损线",
}


def _state(
    *,
    trade_date: date,
    quotes: dict[str, dict[str, Any]],
    index_snapshot: dict[str, Any] | None,
    candidates: list[tuple[AgentTradePlan, dict[str, Any], L0Result]],
) -> dict[str, Any]:
    """L1 判断的行情状态上下文（state 自由形状，随调用透传给判断模型）。

    state 只放题面需要的字段：``plans`` 逐触发计划给方向/触发原因/触发位
    与现价对比，判断模型不再对着纯行情盲答（§11.3 state 纪律）。
    """
    plans: dict[str, dict[str, Any]] = {}
    for plan, quote, l0 in candidates:
        levels: dict[str, Any] = {"stop_loss": float(plan.stop_loss)}
        if plan.plan_type == "buy":
            if plan.buy_zone_low is not None:
                levels["buy_zone_low"] = float(plan.buy_zone_low)
            if plan.buy_zone_high is not None:
                levels["buy_zone_high"] = float(plan.buy_zone_high)
        elif plan.target_price is not None:
            levels["target_price"] = float(plan.target_price)
        plans[str(plan.id)] = {
            "stock_code": plan.stock_code,
            "direction": "买入" if plan.plan_type == "buy" else "卖出",
            "trigger": _TRIGGER_LABELS.get(l0.trigger_reason or "", l0.trigger_reason),
            "levels": levels,
            "price": quote.get("price"),
            "change_pct": quote.get("change_pct"),
        }
    return {
        "trade_date": trade_date.isoformat(),
        "plans": plans,
        "quotes": {
            code: {
                "price": q.get("price"),
                "prev_close": q.get("prev_close"),
                "change_pct": q.get("change_pct"),
            }
            for code, q in quotes.items()
        },
        "index": index_snapshot,
    }


def _questions(
    candidates: list[tuple[AgentTradePlan, dict[str, Any], L0Result]],
) -> dict[str, JudgeQuestion]:
    """触发计划的批量题面：每计划三题（动作 Choice 按方向分变体 + 分时 Noul + 大盘 Score）。"""
    questions: dict[str, JudgeQuestion] = {}
    for plan, _quote, _l0 in candidates:
        key = str(plan.id)
        questions[f"{key}:action"] = (
            CHOICE_INTRADAY_ACTION_BUY
            if plan.plan_type == "buy"
            else CHOICE_INTRADAY_ACTION_SELL
        )
        questions[f"{key}:noul"] = NOUL_BUY_TIMING if plan.plan_type == "buy" else NOUL_EXIT_TIMING
        questions[f"{key}:score"] = SCORE_MARKET_SUPPORT
    return questions


async def _thresholds_for(session: AsyncSession, config_id: int | None) -> DecisionThresholds:
    """按实际服务的配置行解析阈值组（响应 config_id 归因；缺省回起步档）。"""
    if config_id is None:
        return DEFAULT_THRESHOLDS
    row = await session.get(LLMConfig, config_id)
    if row is None:
        return DEFAULT_THRESHOLDS
    try:
        return thresholds_from_extra(row.extra or {})
    except DecisionModelError:
        logger.warning("intraday_thresholds_invalid", config_id=config_id)
        return DEFAULT_THRESHOLDS


def _choice_answer(answers: dict[str, JudgeAnswer] | None, plan_id: int) -> tuple[str, float] | None:
    """提取动作 Choice 答案（选中项 + confidence）；无答案返回 None。"""
    if answers is None:
        return None
    answer = answers.get(f"{plan_id}:action")
    if answer is not None and answer.type == "choice":
        return answer.choice, answer.confidence
    return None


def _answers_payload(
    answers: dict[str, JudgeAnswer] | None,
    *,
    served_model: str | None,
    thresholds: DecisionThresholds,
    plan_id: int,
) -> dict[str, Any]:
    """观测行 decision_answers 载荷：L1 原始答案 + 阈值组 + served 版本。"""
    payload: dict[str, Any] = {
        "served_model": served_model,
        "thresholds": thresholds.model_dump(),
    }
    for suffix in ("action", "noul", "score"):
        answer = answers.get(f"{plan_id}:{suffix}") if answers else None
        if answer is not None:
            payload[suffix] = answer.model_dump()
    return payload


def _decide(
    l0: L0Result,
    choice: tuple[str, float] | None,
    thresholds: DecisionThresholds,
    *,
    plan_type: str,
) -> tuple[str | None, str | None]:
    """L2 判定：L0 结论 + L1 答案按阈值分档 → (action, suppression_reason)。

    execute 闸门按计划方向分档：买入开仓维持资金动作档（fund_action，
    保守）；卖出离场降档至 exit_action——离场是防御动作，错做代价（少赚
    反弹）远小于不做代价（继续承损），不要求与开仓同等置信。
    """
    if l0.verdict == L0_TRIGGERED:
        if choice is None:
            return ACTION_SUPPRESS, SUPPRESS_MODEL_DEGRADED
        picked, confidence = choice
        gate = thresholds.exit_action if plan_type == "sell" else thresholds.fund_action
        if picked == CHOICE_ACTION_EXECUTE and confidence >= gate:
            return ACTION_EXECUTE, None
        if picked == CHOICE_ACTION_ABANDON:
            return ACTION_ABANDON, None
        if confidence < thresholds.observe:
            return ACTION_SUPPRESS, SUPPRESS_BELOW_THRESHOLD
        return ACTION_WAIT, None
    if l0.verdict == L0_NEAR_TRIGGER:
        return ACTION_WAIT, None
    if l0.verdict == L0_DEGRADED:
        return ACTION_SUPPRESS, SUPPRESS_MODEL_DEGRADED
    if l0.reject:
        return ACTION_SUPPRESS, SUPPRESS_L0_REJECT
    return None, None


async def _buy_volume(account: PaperTradeAccount, plan: AgentTradePlan, *, price: float) -> int:
    """按 position_pct 目标市值折算整手买入量（科创板最低 200 股）。"""
    from app.services.trading.client import get_client
    from app.services.trading.paper_trade_mappers import normalize_cash_row

    cash = normalize_cash_row(
        await get_client().get_cash(account_service.credentials_for(account)), today_cn()
    )
    nav = float(cash["nav"]) if cash.get("nav") is not None else 0.0
    target_value = nav * float(plan.position_pct) / 100
    if target_value <= 0:
        return 0
    volume = int(target_value / price // 100) * 100
    if plan.stock_code.startswith("68") and 0 < volume < 200:
        volume = 200 if target_value >= 200 * price else 0
    return volume


async def _held_volume(account: PaperTradeAccount, stock_code: str) -> int:
    """当前持仓股数（卖出计划 / 尾盘强检卖出量）。"""
    from app.services.trading.client import get_client
    from app.services.trading.paper_trade_converters import unwrap_rows

    for row in unwrap_rows(
        await get_client().get_positions(account_service.credentials_for(account))
    ):
        if str(row.get("stock_code") or "") == stock_code:
            return int(row.get("volume") or 0)
    return 0


async def _execute_candidate(
    session: AsyncSession,
    agent: TradingAgent,
    account: PaperTradeAccount,
    plan: AgentTradePlan,
    *,
    price: float,
    now: datetime,
) -> tuple[str, str | None, dict[str, Any]]:
    """执行单个触发计划：shadow 只回观测语义；active 真实下单并推进状态机。

    Returns:
        (action, suppression_reason, extra_snapshot)；异常路径收敛为
        suppress + 原因，不中断本 tick 其他计划。

    Raises:
        AgentAccountNotDesignatedError: 由调用方先行解析账户避免。
    """
    if agent.intraday_exec_mode != "active":
        return ACTION_EXECUTE, SUPPRESS_SHADOW, {}
    side = "buy" if plan.plan_type == "buy" else "sell"
    volume = (
        await _buy_volume(account, plan, price=price)
        if side == "buy"
        else await _held_volume(account, plan.stock_code)
    )
    if volume <= 0:
        return ACTION_SUPPRESS, "position_unavailable", {}
    try:
        result = await execute_agent_order(
            session,
            agent,
            symbol=plan.stock_code,
            side=side,
            volume=volume,
            price=price,
            context="scheduled",
            plan_id=plan.id,
            account=account,
        )
    except RiskRejectedError as exc:
        return ACTION_SUPPRESS, SUPPRESS_RISK_REJECTED, {"risk_reasons": str(exc)}
    except (PaperTradeNotConfiguredError, PaperTradeGatewayError) as exc:
        return ACTION_SUPPRESS, SUPPRESS_ORDER_ERROR, {"error": str(exc)}
    await session.execute(
        update(AgentTradePlan)
        .where(AgentTradePlan.id == plan.id)
        .values(
            status="triggered",
            triggered_cl_ord_id=result["cl_ord_id"],
            triggered_at=now,
            updated_at=utc_now(),
        )
    )
    return ACTION_EXECUTE, None, {"cl_ord_id": result["cl_ord_id"], "volume": volume}


async def _account_or_none(
    session: AsyncSession, agent_key: str
) -> PaperTradeAccount | None:
    """agent 专属账户（未绑定返回 None，触发计划按 no_account 抑制）。"""
    try:
        return await account_service.resolve_agent_account(session, agent_key)
    except AgentAccountNotDesignatedError:
        return None


async def run_tick(
    session: AsyncSession,
    *,
    trade_date: date,
    now: datetime,
    quotes: dict[str, dict[str, Any]],
    index_snapshot: dict[str, Any] | None = None,
    recorders: dict[str, AgentRunRecorder] | None = None,
) -> dict[str, int]:
    """执行一次盘中 tick：active Agent 生效计划集（最近一份 ≤ 当日）过 L0→L1→L2→观测。

    判断模型对全部触发计划只发起一次批量 ``ask_decision``；shadow 模式
    不下单，active 模式经 ``execute_agent_order`` 下单并推进计划状态机。
    返回计数器（evaluated/candidates/executed/suppressed/degraded）。
    """
    counters = {
        "evaluated": 0,
        "candidates": 0,
        "executed": 0,
        "shadow_executed": 0,
        "suppressed": 0,
        "degraded": 0,
    }
    agents = await agent_registry.get_active_agents(session)
    plan_dates = await _effective_plan_dates(session, trade_date)
    for agent in agents:
        recorder = (recorders or {}).get(agent.agent_key)
        effective_date = plan_dates.get(agent.agent_key)
        if effective_date is None:
            continue
        plans = list(
            await session.scalars(
                select(AgentTradePlan).where(
                    AgentTradePlan.agent_key == agent.agent_key,
                    AgentTradePlan.plan_date == effective_date,
                    AgentTradePlan.status == "active",
                )
            )
        )
        evaluated: list[tuple[AgentTradePlan, dict[str, Any], L0Result]] = []
        for plan in plans:
            quote = quotes.get(plan.stock_code)
            if quote is None:
                continue
            price = float(quote["price"]) if quote.get("price") else 0.0
            if price <= 0:  # 停牌/行情缺失：本 tick 不评判
                continue
            prev_close = float(quote["prev_close"]) if quote.get("prev_close") else None
            stock_name = str(quote["name"]) if quote.get("name") else None
            evaluated.append(
                (
                    plan,
                    quote,
                    evaluate_l0(plan, price=price, prev_close=prev_close, stock_name=stock_name),
                )
            )

        candidates = [row for row in evaluated if row[2].verdict == L0_TRIGGERED]
        counters["evaluated"] += len(evaluated)
        counters["candidates"] += len(candidates)
        if not evaluated:
            continue

        answers: dict[str, JudgeAnswer] | None = None
        served_model: str | None = None
        thresholds = DEFAULT_THRESHOLDS
        if candidates:
            try:
                response = await ask_decision(
                    session,
                    state=_state(
                        trade_date=trade_date,
                        quotes=quotes,
                        index_snapshot=index_snapshot,
                        candidates=candidates,
                    ),
                    questions=_questions(candidates),
                )
                answers = response.answers
                served_model = response.model
                thresholds = await _thresholds_for(session, response.config_id)
            except (DecisionModelError, LLMConfigNotConfiguredError) as exc:
                counters["degraded"] += len(candidates)
                # 降级改写 evaluated（观测循环遍历的是它）：触发计划本 tick 记 degraded
                degraded_ids = {plan.id for plan, _q, _l in candidates}
                evaluated = [
                    (
                        plan,
                        quote,
                        L0Result(L0_DEGRADED, l0.trigger_reason, detail=str(exc)),
                    )
                    if plan.id in degraded_ids
                    else (plan, quote, l0)
                    for plan, quote, l0 in evaluated
                ]
                if recorder is not None:
                    async with recorder.step("model_degraded", "判断模型不可用，本 tick 降级纯 L0"):
                        pass

        account = await _account_or_none(session, agent.agent_key) if candidates else None
        is_shadow = agent.intraday_exec_mode != "active"
        for plan, quote, l0 in evaluated:
            choice = _choice_answer(answers, plan.id)
            action, suppression = _decide(l0, choice, thresholds, plan_type=plan.plan_type)
            extra: dict[str, Any] = {}
            if action == ACTION_EXECUTE:
                if account is None:
                    action, suppression = ACTION_SUPPRESS, SUPPRESS_NO_ACCOUNT
                else:
                    step_cm = (
                        recorder.step("order_place", f"计划 {plan.id} 触发下单 {plan.stock_code}")
                        if recorder
                        else nullcontext()
                    )
                    async with step_cm:
                        action, suppression, extra = await _execute_candidate(
                            session, agent, account, plan, price=float(quote["price"]), now=now
                        )
            if action == ACTION_EXECUTE and suppression is None:
                counters["executed"] += 1
            elif action == ACTION_EXECUTE:
                counters["shadow_executed"] += 1
            elif action == ACTION_SUPPRESS:
                counters["suppressed"] += 1
            session.add(
                PaperTradeExecObservation(
                    tick_time=now,
                    trade_date=trade_date,
                    agent_key=agent.agent_key,
                    plan_id=plan.id,
                    stock_code=plan.stock_code,
                    market_snapshot={
                        "price": quote.get("price"),
                        "prev_close": quote.get("prev_close"),
                        "change_pct": quote.get("change_pct"),
                        "l0_detail": l0.detail,
                        **extra,
                    },
                    l0_verdict=l0.verdict,
                    trigger_reason=l0.trigger_reason,
                    decision_answers=_answers_payload(
                        answers,
                        served_model=served_model,
                        thresholds=thresholds,
                        plan_id=plan.id,
                    ),
                    action=action,
                    suppression_reason=suppression,
                    is_shadow=is_shadow,
                )
            )
        await session.commit()
    return counters


async def run_tail_check(
    session: AsyncSession,
    *,
    trade_date: date,
    now: datetime,
    quotes: dict[str, dict[str, Any]],
    recorders: dict[str, AgentRunRecorder] | None = None,
) -> dict[str, int]:
    """尾盘强检（14:50-15:00，纯 L0）：生效计划集未触发行置 expired + 持仓对止损。

    消费对象与 run_tick 同源（各 Agent 最近一份 ≤ 当日的计划集）；状态
    短路幂等（仅 active 行推进 expired，保证一份计划集只喂一个会话）；
    持仓止损强检覆盖该计划集内有计划的持仓标的（stop_loss 取计划值），
    shadow 只落观测。
    """
    counters = {"expired": 0, "checked": 0, "triggered": 0, "executed": 0}
    agents = await agent_registry.get_active_agents(session)
    plan_dates = await _effective_plan_dates(session, trade_date)
    for agent in agents:
        recorder = (recorders or {}).get(agent.agent_key)
        effective_date = plan_dates.get(agent.agent_key)
        if effective_date is None:
            continue
        result = await session.execute(
            update(AgentTradePlan)
            .where(
                AgentTradePlan.agent_key == agent.agent_key,
                AgentTradePlan.plan_date == effective_date,
                AgentTradePlan.status == "active",
            )
            .values(status="expired", updated_at=utc_now())
        )
        counters["expired"] += int(getattr(result, "rowcount", 0) or 0)

        account = await _account_or_none(session, agent.agent_key)
        if account is None:
            await session.commit()
            continue
        plan_rows = list(
            await session.scalars(
                select(AgentTradePlan).where(
                    AgentTradePlan.agent_key == agent.agent_key,
                    AgentTradePlan.plan_date == effective_date,
                )
            )
        )
        stop_map: dict[str, float] = {}
        for plan in sorted(plan_rows, key=lambda r: r.id):
            stop_map[plan.stock_code] = float(plan.stop_loss)

        is_shadow = agent.intraday_exec_mode != "active"
        for code, stop_loss in stop_map.items():
            quote = quotes.get(code)
            price = float(quote["price"]) if quote and quote.get("price") else 0.0
            if price <= 0:
                continue
            counters["checked"] += 1
            if price > stop_loss:
                continue
            counters["triggered"] += 1
            action: str | None = ACTION_EXECUTE
            suppression: str | None = None
            extra: dict[str, Any] = {}
            if is_shadow:
                suppression = SUPPRESS_SHADOW
            else:
                volume = await _held_volume(account, code)
                step_cm = (
                    recorder.step("tail_stop", f"尾盘止损强检 {code}") if recorder else nullcontext()
                )
                async with step_cm:
                    try:
                        if volume <= 0:
                            action, suppression = ACTION_SUPPRESS, "position_unavailable"
                        else:
                            order = await execute_agent_order(
                                session,
                                agent,
                                symbol=code,
                                side="sell",
                                volume=volume,
                                price=price,
                                context="scheduled",
                                account=account,
                            )
                            extra = {"cl_ord_id": order["cl_ord_id"], "volume": volume}
                            counters["executed"] += 1
                    except (
                        RiskRejectedError,
                        PaperTradeNotConfiguredError,
                        PaperTradeGatewayError,
                    ) as exc:
                        action, suppression = ACTION_SUPPRESS, SUPPRESS_ORDER_ERROR
                        extra = {"error": str(exc)}
            session.add(
                PaperTradeExecObservation(
                    tick_time=now,
                    trade_date=trade_date,
                    agent_key=agent.agent_key,
                    plan_id=None,
                    stock_code=code,
                    market_snapshot={
                        "price": price,
                        "stop_loss": stop_loss,
                        "window": "tail_check",
                        **extra,
                    },
                    l0_verdict=L0_TRIGGERED,
                    trigger_reason=REASON_STOP_LOSS,
                    decision_answers=None,
                    action=action,
                    suppression_reason=suppression,
                    is_shadow=is_shadow,
                )
            )
        await session.commit()
    return counters


async def _effective_plan_dates(
    session: AsyncSession, trade_date: date
) -> dict[str, date]:
    """各 active Agent「≤ trade_date 的最新一份」计划日期。

    计划于 T 日盘后生成（plan_date=T），实际供 T+1 起的盘中会话消费，
    故消费按各 Agent 最近一份而非精确当日匹配；当日尾盘强检会把消费过
    的计划推进 expired，保证一份计划集只喂一个会话、不会跨日复用。
    """
    rows = await session.execute(
        select(AgentTradePlan.agent_key, func.max(AgentTradePlan.plan_date))
        .join(TradingAgent, TradingAgent.agent_key == AgentTradePlan.agent_key)
        .where(TradingAgent.status == "active", AgentTradePlan.plan_date <= trade_date)
        .group_by(AgentTradePlan.agent_key)
    )
    return {str(agent_key): plan_date for agent_key, plan_date in rows.all()}


async def plan_stock_codes(session: AsyncSession, *, trade_date: date) -> set[str]:
    """active Agent 生效计划集（各 agent 最近一份 ≤ 当日）标的集合。

    驻留壳按 tick 拉行情的取数范围；不含 status 过滤（与尾盘强检的
    持仓止损口径一致，已触发/已过期行仍在取数范围内）。
    """
    dates = await _effective_plan_dates(session, trade_date)
    if not dates:
        return set()
    rows = await session.scalars(
        select(AgentTradePlan.stock_code).where(
            tuple_(AgentTradePlan.agent_key, AgentTradePlan.plan_date).in_(
                list(dates.items())
            )
        )
    )
    return {str(code) for code in rows}
