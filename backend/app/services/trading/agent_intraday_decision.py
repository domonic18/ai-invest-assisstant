"""盘中执行链判定核（L0→L2 纯决策，无下单副作用）。

L0 确定性比价（精确比价 + 涨跌停粗校，纯函数）→ L1 判断模型题面组装
（state 计划上下文 + 按方向分变体的批量题面）→ L2 阈值分档（执行闸门
按计划方向分档）。本模块是 ``agent_intraday_service``（编排）与
``agent_intraday_exec``（执行）共享的叶子：只依赖 models/contracts/
questions/risk_control 纯函数，禁止导入同包服务模块。
"""

from dataclasses import dataclass
from datetime import date
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.services.trading.agent_intraday_questions import (
    CHOICE_ACTION_ABANDON,
    CHOICE_ACTION_EXECUTE,
    CHOICE_INTRADAY_ACTION_BUY,
    CHOICE_INTRADAY_ACTION_SELL,
    NOUL_BUY_TIMING,
    NOUL_EXIT_TIMING,
    SCORE_MARKET_SUPPORT,
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
SUPPRESS_POSITION_UNAVAILABLE = "position_unavailable"


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
