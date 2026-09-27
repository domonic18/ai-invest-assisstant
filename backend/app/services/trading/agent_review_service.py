"""交易 Agent 盘后分层复盘服务（日/周/月）。

复盘对象为指定 Agent 的专属账户（本地三表按 ``resolve_agent_account()`` 过滤）；
结果按 (skill_id, input_hash=Agent+账户+周期+窗口) 缓存在 ``ai_analysis_result``
（skill_id='paper-trade-review'），生成路径 redis 锁防重入。LLM 单轮结构化输出
字段全 required（禁默认值铁律），一次输出三层 verdict + 盘面语境 + 方法论验证 +
experiences——分层是批次 9 记忆精准反哺的前提（docs/plan/paper-trading-plan.md
§9）；持久化读模型 ``PaperTradeReviewRecord`` 附带 agent_key（落库时注入，读取按
Agent 过滤）。复盘契约 prompt 装载 per-agent 技能包
``skills/trading-<agent_key>/review_prompt.yaml``（D34 skill 化，配置页可见），
未建目录回退共享 ``trading-default``（镜像 plan_skill_id 模式）。

定时任务 ``paper_trade_review_1610``（heavy）循环 active Agent 生成日度；
周五/月末最后一个交易日由任务内日历判定加发周/月度（cron 表达不了
「最后交易日」）。输入未就绪抛 ``ReviewInputDataNotReadyError`` 由 Celery 退避重试。
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Literal

import structlog
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.core.locking import GENERATION_LOCK_TTL_SECONDS, redis_lock
from app.models.paper_trade import (
    PaperTradeCashSnapshot,
    PaperTradeExecution,
    PaperTradeOrder,
    TradingAgent,
)
from app.models.stock import StockBasic
from app.repositories.review import ai_analysis_repository
from app.services.market.trade_calendar_service import NonTradingDayError, next_trading_day
from app.services.review.market_review_service import ReviewInputDataNotReadyError
from app.services.trading import agent_methodology
from app.services.trading.agent_run_recorder import AgentRunRecorder

logger = structlog.get_logger(__name__)

REVIEW_SKILL_ID = "paper-trade-review"
ReviewPeriod = Literal["day", "week", "month"]
#: Literal 在运行时不可迭代，白名单单独维护（API 入参校验用）
REVIEW_PERIODS: tuple[str, ...] = ("day", "week", "month")


def _error_text(exc: BaseException) -> str:
    """异常转 agent_run.error_msg 文本（类型名 + 消息，截断 2000 字符）。"""
    return f"{type(exc).__name__}: {exc}"[:2000]

#: per-agent 技能包复盘契约文件名（D34 skill 化）
_REVIEW_PROMPT_FILE = "review_prompt.yaml"


def review_prompt_skill_id(agent_key: str) -> str:
    """Agent 复盘契约技能包：``skills/trading-<agent_key>/review_prompt.yaml``
    专属作业程序，未建目录时回退共享 ``trading-default``（镜像 plan_skill_id）。"""
    from app.skills import get_skill

    specific = f"trading-{agent_key}"
    return specific if get_skill(specific) is not None else "trading-default"


class PaperTradeReviewLockedError(ConflictError):
    """其他实例正在生成同周期的模拟盘复盘。"""

    default_message = "模拟盘复盘正在生成中，请稍后重试"


class NoReviewTargetError(BadRequestError):
    """agent 账户在复盘窗口内无交易且历史从未成交（无持仓），无复盘对象。"""

    default_message = "agent 账户窗口内无交易且无持仓，无需复盘"


class TradingReviewNotFoundError(NotFoundError):
    """请求的复盘尚未生成。"""


class TradeVerdict(BaseModel):
    """单笔委托的三层判定（字段禁默认值——LLM 必须对每层显式表态）。"""

    cl_ord_id: str
    stock_code: str
    selection_verdict: Literal["correct", "wrong", "neutral"]
    plan_verdict: Literal["correct", "wrong", "neutral"]
    execution_verdict: Literal["correct", "wrong", "neutral"]
    reason: str


class ReviewExperience(BaseModel):
    """复盘提取的经验条目（批次 9 幂等入库 agent_memory 的直接来源）。"""

    title: str
    body: str
    mem_type: Literal["discipline", "method", "lesson"]


class MethodologyCheckItem(BaseModel):
    """单条 KB 纪律的方法论验证结论（逐条表态，禁默认值——LLM 必须对每条显式判定）。"""

    title: str
    verdict: Literal["followed", "violated", "not_applicable"]
    note: str


class PaperTradeReviewContent(BaseModel):
    """复盘 LLM 结构化输出契约（字段禁默认值，进 JSON Schema required）。

    D34 新增 market_context（盘面语境归纳）与 methodology_check（KB 纪律
    逐条验证）；旧缓存行缺这两键由 before-validator 补空值兼容读取。
    """

    period: ReviewPeriod
    trade_date: str
    overall: str
    trades: list[TradeVerdict]
    bias: str
    suggestion: str
    market_context: str
    methodology_check: list[MethodologyCheckItem]
    experiences: list[ReviewExperience]

    @model_validator(mode="before")
    @classmethod
    def _backfill_d34_keys(cls, value: Any) -> Any:
        """D34 前生成的缓存行缺 market_context/methodology_check：补空值兼容
        （skill_id/input_hash 未变，旧复盘必须可读；校验器不影响 LLM schema）。"""
        if isinstance(value, dict):
            value = {**value}
            value.setdefault("market_context", "")
            value.setdefault("methodology_check", [])
        return value

    @field_validator("suggestion", mode="before")
    @classmethod
    def _join_suggestion_list(cls, value: Any) -> Any:
        """「不超过 3 条」会诱导 LLM 输出数组：容忍 list 归一为多行文本。"""
        if isinstance(value, list):
            return "\n".join(str(item) for item in value)
        return value

    @field_validator("experiences", mode="before")
    @classmethod
    def _normalize_experience_keys(cls, value: Any) -> Any:
        """MiniMax 对 output_format 的字段名遵循度差（trigger/action 代
        title/body）：边界处按别名归一，避免整次生成作废重烧。"""
        if isinstance(value, list):
            normalized: list[Any] = []
            for item in value:
                if isinstance(item, dict) and "title" not in item and "trigger" in item:
                    item = {
                        **item,
                        "title": item["trigger"],
                        "body": item.get("action") or item.get("body", ""),
                    }
                    item.pop("trigger", None)
                    item.pop("action", None)
                normalized.append(item)
            return normalized
        return value


class PaperTradeReviewRecord(PaperTradeReviewContent):
    """复盘持久化读模型（structured_output 实际形状）：LLM 契约 + 落库时
    注入的 agent_key（读取按 Agent 过滤；不进 LLM schema）。"""

    agent_key: str


@dataclass(slots=True)
class ReviewGenerateResult:
    """生成结果：内容 + 是否缓存命中（任务 metadata 用）。"""

    content: PaperTradeReviewContent
    cached: bool


def resolve_window(period: ReviewPeriod, trade_date: date) -> tuple[date, date]:
    """按周期解析复盘窗口：day=当日；week=本周一至今；month=本月 1 日至今。"""
    if period == "day":
        return trade_date, trade_date
    if period == "week":
        return trade_date - timedelta(days=trade_date.weekday()), trade_date
    return trade_date.replace(day=1), trade_date


def _input_hash(agent_key: str, account_id: int, period: str, start: date, end: date) -> str:
    raw = (
        f"{REVIEW_SKILL_ID}:{agent_key}:{account_id}:"
        f"{period}:{start.isoformat()}:{end.isoformat()}"
    )
    return hashlib.sha256(raw.encode()).hexdigest()


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


async def get_review(
    session: AsyncSession,
    agent_key: str,
    *,
    period: ReviewPeriod,
    trade_date: date | None = None,
) -> PaperTradeReviewRecord | None:
    """读取指定 Agent 已生成的复盘（不触发 LLM）；trade_date 缺省取最新交易日。"""
    from app.services.market import trade_calendar_service
    from app.services.trading import account_service

    resolved = trade_date or await trade_calendar_service.resolve_latest_trade_date(
        session
    )
    account = await account_service.resolve_agent_account(session, agent_key)
    start, end = resolve_window(period, resolved)
    row = await ai_analysis_repository.load_latest_success(
        session,
        skill_id=REVIEW_SKILL_ID,
        trade_date=resolved,
        input_hash=_input_hash(agent_key, account.id, period, start, end),
    )
    if row is None or not row.structured_output:
        return None
    return PaperTradeReviewRecord.model_validate(row.structured_output)


async def list_review_dates(
    session: AsyncSession, agent_key: str, *, period: ReviewPeriod
) -> list[date]:
    """指定 Agent 已生成该周期复盘的基准交易日（升序），日历打点用。"""
    return await ai_analysis_repository.list_success_trade_dates(
        session,
        skill_id=REVIEW_SKILL_ID,
        structured_filter={"period": period, "agent_key": agent_key},
    )


async def generate_review(
    session: AsyncSession,
    agent: TradingAgent,
    *,
    period: ReviewPeriod,
    trade_date: date | None = None,
    regenerate: bool = False,
    trigger: str = "scheduled",
    collector_log_id: int | None = None,
) -> ReviewGenerateResult:
    """生成（或读取缓存的）指定 Agent 的模拟盘分层复盘。

    全程经 ``AgentRunRecorder`` 记录执行轨迹（D35 会话管理）：缓存命中落
    skipped + cache_hit，异常落 failed 后原样上抛。

    Raises:
        NonTradingDayError: 指定日期不是交易日
        AgentAccountNotDesignatedError: 该 Agent 未绑定专属账户
        NoReviewTargetError: 窗口内无交易且无持仓
        ReviewInputDataNotReadyError: 盘后同步尚未落库（Celery 退避重试）
        PaperTradeReviewLockedError: 其他实例正在生成
    """
    from app.services.market import trade_calendar_service
    from app.services.trading import account_service

    if trade_date is not None and not await trade_calendar_service.is_trading_day(
        session, trade_date
    ):
        raise NonTradingDayError(
            f"{trade_date.isoformat()} 不是交易日，模拟盘复盘只对交易日有效"
        )
    resolved = trade_date or await trade_calendar_service.resolve_latest_trade_date(
        session
    )
    account = await account_service.resolve_agent_account(session, agent.agent_key)
    start, end = resolve_window(period, resolved)
    input_hash = _input_hash(agent.agent_key, account.id, period, start, end)

    recorder = AgentRunRecorder(
        agent_key=agent.agent_key,
        kind="review",
        period=period,
        trigger=trigger,
        trade_date=resolved,
        collector_log_id=collector_log_id,
    )
    await recorder.start()
    try:
        if not regenerate:
            cached = await _load_cached(session, input_hash)
            if cached:
                await recorder.finish(
                    "skipped", summary={"cache_hit": True, "stage": "pre_lock"}
                )
                return ReviewGenerateResult(content=cached, cached=True)

        sync_landed = False
        has_target = False
        async with recorder.step(
            "precheck",
            "执行预检（盘后同步/复盘对象）",
            payload_builder=lambda: {
                "trade_date": resolved.isoformat(),
                "window": [start.isoformat(), end.isoformat()],
                "account_id": account.id,
                "sync_landed": sync_landed,
                "has_review_target": has_target,
            },
        ):
            sync_landed = await _sync_landed(session, account.id, resolved)
            if not sync_landed:
                raise ReviewInputDataNotReadyError(
                    f"{resolved.isoformat()} 盘后同步尚未落库，模拟盘复盘输入未就绪"
                )
            has_target = await _has_review_target(session, account.id, start, end)
            if not has_target:
                raise NoReviewTargetError(
                    f"agent 账户在 {start.isoformat()}~{end.isoformat()} 无交易且无持仓"
                )

        async with redis_lock(
            f"{REVIEW_SKILL_ID}:{agent.agent_key}:{account.id}:{period}:{resolved.isoformat()}",
            ttl=GENERATION_LOCK_TTL_SECONDS,
        ) as acquired:
            if not acquired:
                cached = await _load_cached(session, input_hash)
                if cached:
                    await recorder.finish(
                        "skipped",
                        summary={"cache_hit": True, "stage": "lock_unavailable"},
                    )
                    return ReviewGenerateResult(content=cached, cached=True)
                await recorder.finish(
                    "failed",
                    error_msg=(
                        f"其他实例正在生成 {resolved.isoformat()} 的 {period} 复盘"
                    ),
                )
                raise PaperTradeReviewLockedError(
                    f"其他实例正在生成 {resolved.isoformat()} 的 {period} 复盘"
                )

            if not regenerate:
                cached = await _load_cached(session, input_hash)
                if cached:
                    await recorder.finish(
                        "skipped", summary={"cache_hit": True, "stage": "in_lock"}
                    )
                    return ReviewGenerateResult(content=cached, cached=True)

            window_input: dict[str, Any] = {}
            async with recorder.step(
                "input.window",
                "复盘窗口取数（委托/成交/净值）",
                payload_builder=lambda: window_input or None,
            ):
                window_input = await _collect_window_input(
                    session, account.id, start, end
                )

            market_review: dict[str, Any] | None = None
            async with recorder.step(
                "input.market_review",
                "大盘复盘解读（盘面语境）",
                payload_builder=lambda: {"sections": market_review},
            ):
                market_review = await _market_review_optional(session, resolved)
            window_input["market_review"] = market_review

            methodology: dict[str, Any] | None = None
            async with recorder.step(
                "input.methodology",
                "方法论基座检索（KB 直读）",
                payload_builder=lambda: {
                    "source_id": agent.methodology_source_id,
                    "methodology": methodology,
                },
            ):
                methodology = await agent_methodology.build_methodology_input(
                    session, source_id=agent.methodology_source_id, query_text=None
                )
            window_input["methodology"] = methodology

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
                    period,
                    resolved,
                    window_input,
                    meta_out=llm_meta,
                    prompt_out=prompt_holder,
                )
                output_holder["output"] = content.model_dump(mode="json")

            dropped_cl: list[str] = []
            async with recorder.step(
                "validate",
                "后置校验（幻觉委托剔除）",
                payload_builder=lambda: {
                    "dropped_cl_ord_ids": dropped_cl,
                    "trades": len(content.trades),
                },
            ):
                content = _validate(
                    content, {o["cl_ord_id"] for o in window_input["orders"]}
                )
                dropped_cl = sorted(
                    {
                        t["cl_ord_id"]
                        for t in output_holder["output"].get("trades", [])
                        if isinstance(t, dict) and "cl_ord_id" in t
                    }
                    - {t.cl_ord_id for t in content.trades}
                )

            record = PaperTradeReviewRecord(
                **content.model_dump(), agent_key=agent.agent_key
            )

            async with recorder.step(
                "persist",
                "落库（ai_analysis_result 缓存行）",
                payload_builder=lambda: {
                    "trades": len(record.trades),
                    "experiences": len(record.experiences),
                    "methodology_check": len(record.methodology_check),
                },
            ):
                await _persist(
                    session, input_hash=input_hash, content=record, meta=llm_meta
                )

        await recorder.finish(
            "success",
            summary={
                "cache_hit": False,
                "regenerate": regenerate,
                "kb_used": bool(methodology),
                "trades": len(record.trades),
                "experiences": len(record.experiences),
                "methodology_check": len(record.methodology_check),
                "model": llm_meta.get("model_name"),
                "latency_ms": llm_meta.get("latency_ms"),
            },
        )
        return ReviewGenerateResult(content=record, cached=False)
    except Exception as exc:
        await recorder.finish("failed", error_msg=_error_text(exc))
        raise


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


async def _load_cached(
    session: AsyncSession, input_hash: str
) -> PaperTradeReviewRecord | None:
    row = await ai_analysis_repository.load_latest_success(
        session, skill_id=REVIEW_SKILL_ID, input_hash=input_hash
    )
    if row is None or not row.structured_output:
        return None
    return PaperTradeReviewRecord.model_validate(row.structured_output)


async def _run_llm(
    session: AsyncSession,
    agent: TradingAgent,
    period: str,
    trade_date: date,
    window_input: dict[str, Any],
    *,
    meta_out: dict[str, Any] | None = None,
    prompt_out: dict[str, str] | None = None,
) -> PaperTradeReviewContent:
    from app.skills import load_named_skill_prompt

    config = load_named_skill_prompt(
        review_prompt_skill_id(agent.agent_key), _REVIEW_PROMPT_FILE
    )
    # 人设段空值行跳过（D30：新建 Agent 仅填名称即可）
    identity = f"- 你是{agent.name}" + (f"（{agent.tagline}）" if agent.tagline else "")
    persona_lines = [identity, "- 以该人设的视角与风格生成分层复盘结论"]
    user_prompt = (
        f"{config.system_prompt}\n\n"
        f"## 复盘人设（注册表行，D27/D34）\n"
        + "\n".join(persona_lines)
        + "\n\n"
        f"## 复盘任务\n"
        f"- 周期 period：{period}\n"
        f"- 基准交易日 trade_date：{trade_date.isoformat()}（输出字段须原样带回）\n\n"
        f"## 复盘输入数据（JSON：agent 账户本地委托/成交/资金快照 + market_review "
        f"盘面语境 + methodology 方法论基座）\n"
        f"{json.dumps(window_input, ensure_ascii=False, default=str)}"
    )
    if prompt_out is not None:
        prompt_out["prompt"] = user_prompt
    from app.agent.runtime.structured import run_structured

    return await run_structured(
        session,
        result_type=PaperTradeReviewContent,
        user_prompt=user_prompt,
        config_id=agent.llm_config_id,
        meta_out=meta_out,
    )


def _validate(
    content: PaperTradeReviewContent, valid_cl_ord_ids: set[str]
) -> PaperTradeReviewContent:
    """后置校验：trades.cl_ord_id 必须来自窗口内真实委托（剔除幻觉行）。"""
    trades = [t for t in content.trades if t.cl_ord_id in valid_cl_ord_ids]
    return content.model_copy(update={"trades": trades})


async def _persist(
    session: AsyncSession,
    *,
    input_hash: str,
    content: Any,
    meta: dict[str, Any] | None = None,
) -> None:
    """落缓存行；meta 携带 run_structured 的 model_name/latency_ms（D35 补全）。"""
    meta = meta or {}
    await ai_analysis_repository.insert_result(
        session,
        skill_id=REVIEW_SKILL_ID,
        input_hash=input_hash,
        prompt_id=REVIEW_SKILL_ID,
        model=meta.get("model_name"),
        structured=content.model_dump(mode="json"),
        latency_ms=int(meta.get("latency_ms") or 0),
        status="success",
    )
    await session.commit()


async def is_last_trading_day_of_week(session: AsyncSession, day: date) -> bool:
    """day 之后最近的交易日是否已跨入下一周（ISO 周）——周五遇休市时周四即为周期末。"""
    nxt = await next_trading_day(session, day)
    return nxt is None or nxt.isocalendar()[:2] != day.isocalendar()[:2]


async def is_last_trading_day_of_month(session: AsyncSession, day: date) -> bool:
    """day 之后最近的交易日是否已跨入下一月。"""
    nxt = await next_trading_day(session, day)
    return nxt is None or (nxt.year, nxt.month) != (day.year, day.month)
