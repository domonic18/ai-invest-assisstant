"""交易 Agent 每日选股与交易计划生成服务（批次 7，plan §10.2 编排层）。

19:30 定时生成（D30 重排：晚于 agent 复盘 19:00，先复盘后选股）：输入 =
当日复盘解读（18:35 后就绪，缺失即退避重试）+
涨停归因 + 异动归因 + agent 持仓 + 人工移出清单 + 方法论基座（KB 直读）+
经验记忆（``agent_plan_input.collect_plan_input`` 组装）→ LLM 单轮结构化
输出（契约见 ``agent_plan_schemas``）→ 幻觉/人工移出代码后置校验 → 缓存行
+ 两表 upsert（``agent_plan_persist``）。按 (skill_id, input_hash=Agent+
账户+交易日) 缓存 ``ai_analysis_result``，redis 锁防重入；多 Agent 各自
独立生成（agent-hub-plan.md D23）。计划 prompt 装载 per-agent 技能包
``skills/trading-<agent_key>/prompt.yaml``（D27），未建目录回退共享
``trading-default``（D28 扩展性：新 Agent 免建技能目录）；user_prompt 头部
注入注册表人设段（D28 全链路）。
"""

import hashlib
import json
from datetime import date
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.core.locking import GENERATION_LOCK_TTL_SECONDS, redis_lock
from app.models.paper_trade import TradingAgent
from app.models.stock import StockBasic
from app.repositories.review import ai_analysis_repository
from app.services.trading import account_service, agent_plan_input, agent_plan_persist
from app.services.trading.agent_plan_schemas import (
    AgentDailyPlanContent,
    PlanGenerateResult,
    PlanTradePlanItem,
)
from app.services.trading.agent_run_recorder import AgentRunRecorder
from app.skills import load_skill_prompt

logger = structlog.get_logger(__name__)

#: plan_cadence（注册行）→ agent_run.period 列映射（day/week/month）
_CADENCE_PERIODS = {"daily": "day", "weekly": "week", "monthly": "month"}

# 价格体检阈值（确定性校验，非模型判断；治幻觉价格的事后兜底，供给侧锚点
# 由 agent_plan_input.price_anchors 承担）
#: buy 区间合理窗口：与 [prev_close×0.7, prev_close×1.1] 无交集即脱锚
_PRICE_WINDOW_LOW = 0.7
_PRICE_WINDOW_HIGH = 1.1
#: 止损下限：低于区间下沿 ×0.85 视为远超常理的「破位即弃」
_STOP_FLOOR_RATIO = 0.85


def plan_skill_id(agent_key: str) -> str:
    """Agent 每日计划技能 ID：``skills/trading-<agent_key>/`` 专属作业程序，
    未建目录时回退共享 ``trading-default``（D28 扩展性：新 Agent 免建目录）。"""
    from app.skills import get_skill

    specific = f"trading-{agent_key}"
    return specific if get_skill(specific) is not None else "trading-default"


class PlanGenerationLockedError(ConflictError):
    """其他实例正在生成同日交易计划。"""

    default_message = "交易计划正在生成中，请稍后重试"


def _error_text(exc: BaseException) -> str:
    """异常转 agent_run.error_msg 文本（类型名 + 消息，截断 2000 字符）。"""
    return f"{type(exc).__name__}: {exc}"[:2000]


def _input_hash(agent_key: str, account_id: int, trade_date: date) -> str:
    raw = (
        f"{plan_skill_id(agent_key)}:{agent_key}:{account_id}:"
        f"{trade_date.isoformat()}"
    )
    return hashlib.sha256(raw.encode()).hexdigest()


async def _load_cached(
    session: AsyncSession, skill_id: str, input_hash: str
) -> AgentDailyPlanContent | None:
    row = await ai_analysis_repository.load_latest_success(
        session, skill_id=skill_id, input_hash=input_hash
    )
    if row is None or not row.structured_output:
        return None
    structured = row.structured_output
    if isinstance(structured, dict) and "stand_aside_reason" not in structured:
        # 新增字段前的旧缓存快照：补键兼容（模型契约本身要求该键存在）
        structured = {**structured, "stand_aside_reason": None}
    return AgentDailyPlanContent.model_validate(structured)


async def _run_llm(
    session: AsyncSession,
    agent: TradingAgent,
    trade_date: date,
    plan_input: dict,
    *,
    meta_out: dict[str, Any] | None = None,
    prompt_out: dict[str, str] | None = None,
) -> AgentDailyPlanContent:
    config = load_skill_prompt(plan_skill_id(agent.agent_key))
    # 人设段空值行跳过（D30：新建 Agent 仅填名称即可）
    identity = f"- 你是{agent.name}" + (f"（{agent.tagline}）" if agent.tagline else "")
    persona_lines = [identity]
    persona_lines.append("- 以该人设的视角与风格生成选股与交易计划")
    user_prompt = (
        f"{config.system_prompt}\n\n"
        f"## 计划人设（注册表行，D27/D28）\n"
        + "\n".join(persona_lines)
        + "\n\n"
        f"## 计划任务\n"
        f"- 基准交易日 trade_date：{trade_date.isoformat()}（输出字段须原样带回）\n"
        f"- 若当日确实无可选标的、无开仓机会且无需持仓管理（如系统性风险、无符合\n"
        f"  纪律的买点），selections 与 plans 输出空数组，并必须在\n"
        f"  stand_aside_reason 给出简明的空仓观望原因；任一数组非空时该字段为 null。\n\n"
        f"## 计划输入数据（JSON）\n"
        f"{json.dumps(plan_input, ensure_ascii=False, default=str)}"
    )
    if prompt_out is not None:
        prompt_out["prompt"] = user_prompt
    from app.agent.runtime.structured import run_structured

    return await run_structured(
        session,
        result_type=AgentDailyPlanContent,
        user_prompt=user_prompt,
        config_id=agent.llm_config_id,
        meta_out=meta_out,
    )


async def _validate_codes(
    session: AsyncSession, content: AgentDailyPlanContent, manual_removed: list[str]
) -> tuple[AgentDailyPlanContent, list[str]]:
    """后置校验：剔除 stock_basic 不存在的幻觉代码与人工移出代码。

    剔除后若转为双空（原输出有标的但全被剔），回填空仓原因——契约要求
    双空必有 stand_aside_reason，且展示层据此区分「空仓观望」与「未生成」。
    """
    codes = {s.stock_code for s in content.selections} | {
        p.stock_code for p in content.plans
    }
    rows = await session.execute(
        select(StockBasic.stock_code).where(StockBasic.stock_code.in_(codes))
    )
    valid = set(rows.scalars().all())
    dropped = sorted(codes - valid) + [
        code for code in manual_removed if code in codes
    ]
    keep = valid - set(manual_removed)
    selections = [s for s in content.selections if s.stock_code in keep]
    plans = [p for p in content.plans if p.stock_code in keep]
    update: dict[str, Any] = {"selections": selections, "plans": plans}
    if (
        not selections
        and not plans
        and not (content.stand_aside_reason or "").strip()
        and dropped
    ):
        update["stand_aside_reason"] = (
            f"后置校验剔除无效代码：{'、'.join(dropped)}，当日转为空仓观望"
        )
    content = content.model_copy(update=update)
    return content, dropped


def _validate_prices(
    content: AgentDailyPlanContent,
    anchors: dict[str, dict[str, Any]],
) -> tuple[AgentDailyPlanContent, dict[str, str]]:
    """确定性价格体检（纯函数零 LLM）：剔除与锚点严重脱锚的 buy 计划/选股。

    buy 规则（prev_close 来自锚点）：止损不低于昨收、区间不倒挂、区间与
    合理窗口 ``[prev_close×0.7, prev_close×1.1]`` 有交集、止损不深于区间下沿
    ×0.85。sell 是防御动作不因数据缺口剔除，仅在止盈/止损齐备且倒挂时剔除；
    无锚点的持仓标的 sell 计划放行（ protective exit 不被数据缺口废掉）。

    Returns:
        (校验后内容, {代码: 违规原因})；剔除后转双空时回填空仓原因。
    """
    violations: dict[str, str] = {}
    for plan in content.plans:
        anchor = anchors.get(plan.stock_code)
        if plan.plan_type == "buy":
            if anchor is None or not anchor.get("prev_close"):
                violations[plan.stock_code] = "缺价格锚点，禁止出买点计划"
                continue
            prev_close = float(anchor["prev_close"])
            reason = _buy_plan_price_violation(plan, prev_close)
            if reason:
                violations[plan.stock_code] = reason
            continue
        # sell：轻校验（止盈止损同时给出才可比）
        if (
            plan.target_price is not None
            and plan.target_price <= plan.stop_loss
        ):
            violations[plan.stock_code] = (
                f"sell 止盈 {plan.target_price} 不高于止损 {plan.stop_loss}"
            )

    keep_buy = {code for code in anchors} - set(violations)
    selections = [
        s for s in content.selections if s.stock_code in keep_buy
    ]
    plans = [
        p
        for p in content.plans
        if p.plan_type == "sell" or p.stock_code in keep_buy
    ]
    update: dict[str, Any] = {"selections": selections, "plans": plans}
    if (
        not selections
        and not plans
        and not (content.stand_aside_reason or "").strip()
        and violations
    ):
        detail = "；".join(f"{code}（{why}）" for code, why in violations.items())
        update["stand_aside_reason"] = f"价格体检剔除脱锚计划：{detail}，当日转为空仓观望"
    return content.model_copy(update=update), violations


def _buy_plan_price_violation(plan: PlanTradePlanItem, prev_close: float) -> str | None:
    """单条 buy 计划的价格体检（首条违规即返回）。"""
    if plan.stop_loss >= prev_close:
        return f"止损 {plan.stop_loss} 不低于昨收 {prev_close}"
    low = plan.buy_zone_low
    high = plan.buy_zone_high
    if low is None or high is None:
        return "buy 计划缺买点区间"
    if low > high:
        return f"买点区间倒挂 [{low}, {high}]"
    window_low = prev_close * _PRICE_WINDOW_LOW
    window_high = prev_close * _PRICE_WINDOW_HIGH
    if high < window_low or low > window_high:
        return (
            f"区间 [{low}, {high}] 与合理窗口 [{window_low:.2f}, {window_high:.2f}]"
            f"（昨收 {prev_close}）无交集"
        )
    if float(plan.stop_loss) < float(low) * _STOP_FLOOR_RATIO:
        return f"止损 {plan.stop_loss} 深于区间下沿 {low} 的 {_STOP_FLOOR_RATIO:g} 倍"
    return None


async def generate_daily_plan(
    session: AsyncSession,
    agent: TradingAgent,
    *,
    trade_date: date | None = None,
    regenerate: bool = False,
    trigger: str = "scheduled",
    collector_log_id: int | None = None,
) -> PlanGenerateResult:
    """生成（或读取缓存的）指定 Agent 当日选股与交易计划。

    全程经 ``AgentRunRecorder`` 记录执行轨迹（D35 会话管理）：缓存命中落
    skipped + cache_hit，异常落 failed 后原样上抛。

    Raises:
        NonTradingDayError: 指定日期不是交易日
        AgentAccountNotDesignatedError: 该 Agent 未绑定专属账户
        PaperTradeNotConfiguredError: paper_trade_url 未配置（模拟盘整体未启用）
        ReviewInputDataNotReadyError: 当日复盘解读尚未生成（Celery 退避重试）
        PlanGenerationLockedError: 其他实例正在生成
    """
    from app.core.config import get_settings
    from app.services.market import trade_calendar_service
    from app.services.trading.errors import PaperTradeNotConfiguredError

    if not get_settings().paper_trade_url:
        raise PaperTradeNotConfiguredError()
    if trade_date is not None and not await trade_calendar_service.is_trading_day(
        session, trade_date
    ):
        raise trade_calendar_service.NonTradingDayError(
            f"{trade_date.isoformat()} 不是交易日，每日计划只对交易日有效"
        )
    resolved = trade_date or await trade_calendar_service.resolve_latest_trade_date(
        session
    )
    account = await account_service.resolve_agent_account(session, agent.agent_key)
    skill_id = plan_skill_id(agent.agent_key)
    input_hash = _input_hash(agent.agent_key, account.id, resolved)

    recorder = AgentRunRecorder(
        agent_key=agent.agent_key,
        kind="plan",
        period=_CADENCE_PERIODS.get(agent.plan_cadence),
        trigger=trigger,
        trade_date=resolved,
        collector_log_id=collector_log_id,
    )
    await recorder.start()
    try:
        if not regenerate:
            cached = await _load_cached(session, skill_id, input_hash)
            if cached:
                await recorder.finish(
                    "skipped", summary={"cache_hit": True, "stage": "pre_lock"}
                )
                return PlanGenerateResult(
                    content=cached, cached=True, dropped_codes=[]
                )

        async with recorder.step(
            "precheck",
            "执行预检",
            payload_builder=lambda: {
                "trade_date": resolved.isoformat(),
                "account_id": account.id,
                "skill_id": skill_id,
                "regenerate": regenerate,
            },
        ):
            pass

        # 输入组装（内含就绪预检：复盘解读缺失即抛未就绪）
        plan_input, manual_removed = await agent_plan_input.collect_plan_input(
            session, agent, account.id, resolved, recorder=recorder
        )

        async with redis_lock(
            f"{skill_id}:{agent.agent_key}:{account.id}:{resolved.isoformat()}",
            ttl=GENERATION_LOCK_TTL_SECONDS,
        ) as acquired:
            if not acquired:
                cached = await _load_cached(session, skill_id, input_hash)
                if cached:
                    await recorder.finish(
                        "skipped",
                        summary={"cache_hit": True, "stage": "lock_unavailable"},
                    )
                    return PlanGenerateResult(
                        content=cached, cached=True, dropped_codes=[]
                    )
                await recorder.finish(
                    "failed",
                    error_msg=f"其他实例正在生成 {resolved.isoformat()} 的每日计划",
                )
                raise PlanGenerationLockedError(
                    f"其他实例正在生成 {resolved.isoformat()} 的每日计划"
                )

            if not regenerate:
                cached = await _load_cached(session, skill_id, input_hash)
                if cached:
                    await recorder.finish(
                        "skipped", summary={"cache_hit": True, "stage": "in_lock"}
                    )
                    return PlanGenerateResult(
                        content=cached, cached=True, dropped_codes=[]
                    )

            llm_meta: dict[str, Any] = {}
            prompt_holder: dict[str, str] = {}
            output_holder: dict[str, Any] = {}
            async with recorder.step(
                "llm",
                "LLM 结构化生成",
                payload_builder=lambda: {
                    "prompt": prompt_holder.get("prompt"),
                    "meta": llm_meta,
                    "output": output_holder.get("output"),
                },
            ):
                content = await _run_llm(
                    session,
                    agent,
                    resolved,
                    plan_input,
                    meta_out=llm_meta,
                    prompt_out=prompt_holder,
                )
                output_holder["output"] = content.model_dump(mode="json")

            dropped: list[str] = []
            price_violations: dict[str, str] = {}
            async with recorder.step(
                "validate",
                "后置校验（幻觉/人工移出剔除 + 价格体检）",
                payload_builder=lambda: {
                    "dropped_codes": dropped,
                    "price_violations": price_violations,
                    "selections": len(content.selections),
                    "plans": len(content.plans),
                },
            ):
                content, dropped = await _validate_codes(
                    session, content, manual_removed
                )
                content, price_violations = _validate_prices(
                    content, plan_input.get("price_anchors") or {}
                )
                dropped = dropped + sorted(price_violations)

            cache_row_id: int | None = None
            async with recorder.step(
                "persist",
                "落库（缓存行 + 选股/计划两表）",
                payload_builder=lambda: {
                    "cache_row_id": cache_row_id,
                    "selections": len(content.selections),
                    "plans": len(content.plans),
                },
            ):
                cache_row_id = await agent_plan_persist.persist_cache_row(
                    session,
                    skill_id=skill_id,
                    input_hash=input_hash,
                    content=content,
                    meta=llm_meta,
                )
                await agent_plan_persist.persist_plan(
                    session,
                    agent_key=agent.agent_key,
                    trade_date=resolved,
                    content=content,
                    source_result_id=cache_row_id,
                )

        if dropped:
            logger.warning(
                "agent_daily_plan_codes_dropped",
                agent_key=agent.agent_key,
                codes=dropped,
                trade_date=resolved.isoformat(),
            )
        await recorder.finish(
            "success",
            summary={
                "cache_hit": False,
                "regenerate": regenerate,
                "kb_used": bool(plan_input.get("methodology")),
                "selections": len(content.selections),
                "plans": len(content.plans),
                "stand_aside_reason": (content.stand_aside_reason or "")[:100] or None,
                "dropped_codes": dropped,
                "price_violations": price_violations,
                "model": llm_meta.get("model_name"),
                "latency_ms": llm_meta.get("latency_ms"),
            },
        )
        return PlanGenerateResult(content=content, cached=False, dropped_codes=dropped)
    except Exception as exc:
        await recorder.finish("failed", error_msg=_error_text(exc))
        raise


async def load_plan_content_for_date(
    session: AsyncSession, agent_key: str, trade_date: date
) -> AgentDailyPlanContent | None:
    """读取指定日已生成的计划内容缓存（含空仓观望日，供展示层区分空仓/未生成）。

    Agent 未绑定专属账户或该日无成功缓存行返回 None。
    """
    from app.services.trading.errors import AgentAccountNotDesignatedError

    try:
        account = await account_service.resolve_agent_account(session, agent_key)
    except AgentAccountNotDesignatedError:
        return None
    return await _load_cached(
        session,
        plan_skill_id(agent_key),
        _input_hash(agent_key, account.id, trade_date),
    )


async def list_stand_aside_dates(session: AsyncSession, agent_key: str) -> list[date]:
    """空仓观望日清单（已生成计划但选股/计划双空的日期，日历打点补全）。

    plan_dates 源自 AgentTradePlan 行，空仓日两表无行天然缺失，由此按缓存
    行回查。仅专属技能 Agent 支持：input_hash 绑定 account_id，共享
    ``trading-default`` 技能被多 Agent 共用，无法从哈希安全反解账户维度；
    未绑定账户返回 []。
    """
    from app.services.trading.errors import AgentAccountNotDesignatedError

    skill_id = plan_skill_id(agent_key)
    if skill_id == "trading-default":
        return []
    try:
        account = await account_service.resolve_agent_account(session, agent_key)
    except AgentAccountNotDesignatedError:
        return []
    trade_dates = await ai_analysis_repository.list_success_trade_dates(
        session, skill_id=skill_id
    )
    hashes = {d: _input_hash(agent_key, account.id, d) for d in trade_dates}
    rows = await ai_analysis_repository.load_success_by_hashes(
        session, skill_id=skill_id, input_hashes=list(hashes.values())
    )
    by_hash = {h: d for d, h in hashes.items()}
    dates = {
        by_hash[row.input_hash]
        for row in rows
        if row.input_hash in by_hash
        and not (row.structured_output or {}).get("selections")
        and not (row.structured_output or {}).get("plans")
    }
    return sorted(dates)
