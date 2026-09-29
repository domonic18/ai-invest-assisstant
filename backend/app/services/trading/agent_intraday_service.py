"""盘中自主执行链编排（批次 8 PR-1，paper-trading-plan §11 / D21/D24）。

四层栈：L0 确定性判定 → L1 判断模型（一次 ask_decision 批量提问全部触发
计划）→ L2 阈值抑制留痕 → L3 落 ``paper_trade_exec_observation`` 观测行。
判定核（L0→L2 纯决策）在 ``agent_intraday_decision``，broker 触达与未结
对账在 ``agent_intraday_exec``，本模块只做编排：拉 agent/计划集、聚合
行情、推进观测与计数。

``intraday_exec_mode`` 三态语义：``shadow`` 全链路判断留痕不下单（影子期
校准数据集）；``active`` 触发即真实下单并推进计划状态机；``off`` 不进入
本服务。判断模型异常为 advisory 降级：当次 tick 纯 L0，观测记
``model_degraded``，禁止用阈值近似替代判断。
"""

from contextlib import nullcontext
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_now
from app.core.decision_model.contracts import (
    DEFAULT_THRESHOLDS,
    JudgeAnswer,
)
from app.core.decision_model.errors import DecisionModelError
from app.models.agent_trading import AgentTradePlan
from app.models.paper_trade import PaperTradeExecObservation, TradingAgent
from app.services.admin.decision_model_service import ask_decision
from app.services.admin.llm_config_service import LLMConfigNotConfiguredError
from app.services.trading import agent_registry
from app.services.trading.agent_intraday_decision import (
    ACTION_EXECUTE,
    ACTION_SUPPRESS,
    L0_DEGRADED,
    L0_TRIGGERED,
    REASON_STOP_LOSS,
    SUPPRESS_NO_ACCOUNT,
    L0Result,
    _answers_payload,
    _choice_answer,
    _decide,
    _questions,
    _state,
    _thresholds_for,
    evaluate_l0,
)
from app.services.trading.agent_intraday_exec import (
    _account_or_none,
    _execute_candidate,
    _reconcile_pending_orders,
    execute_tail_stop,
)
from app.services.trading.agent_run_recorder import AgentRunRecorder


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

    消费集经 ``get_intraday_agents``（``intraday_paused`` 冻结的 Agent 本 tick
    完全短路：不评判、不下单、不写观测）。判断模型对全部触发计划只发起一次
    批量 ``ask_decision``；shadow 模式不下单，active 模式经 ``execute_agent_order``
    下单并推进计划状态机。返回计数器（evaluated/candidates/executed/suppressed/degraded）。
    """
    counters = {
        "evaluated": 0,
        "candidates": 0,
        "executed": 0,
        "shadow_executed": 0,
        "suppressed": 0,
        "degraded": 0,
    }
    agents = await agent_registry.get_intraday_agents(session)
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
        await _reconcile_pending_orders(session, agent)
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

    消费对象与 run_tick 同源（``get_intraday_agents``，``intraday_paused`` 冻结
    的 Agent 跳过——其计划集不推进 expired、持仓不做止损强检）；状态
    短路幂等（仅 active 行推进 expired，保证一份计划集只喂一个会话）；
    持仓止损强检覆盖该计划集内有计划的持仓标的（stop_loss 取计划值），
    shadow 只落观测。
    """
    counters = {"expired": 0, "checked": 0, "triggered": 0, "executed": 0}
    agents = await agent_registry.get_intraday_agents(session)
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
            step_cm = (
                recorder.step("tail_stop", f"尾盘止损强检 {code}")
                if recorder and not is_shadow
                else nullcontext()
            )
            async with step_cm:
                action, suppression, extra = await execute_tail_stop(
                    session, agent, account, stock_code=code, price=price
                )
            if action == ACTION_EXECUTE and suppression is None:
                counters["executed"] += 1
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
        await _reconcile_pending_orders(session, agent)
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
