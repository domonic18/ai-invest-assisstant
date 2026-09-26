"""交易 Agent 盘后分层复盘服务（日/周/月）。

复盘对象为指定 Agent 的专属账户（本地三表按 ``resolve_agent_account()`` 过滤）；
结果按 (skill_id, input_hash=Agent+账户+周期+窗口) 缓存在 ``ai_analysis_result``
（skill_id='paper-trade-review'），生成路径 redis 锁防重入。LLM 单轮结构化输出
字段全 required（禁默认值铁律），一次输出三层 verdict + experiences——分层是
批次 9 记忆精准反哺的前提（docs/plan/paper-trading-plan.md §9）；持久化读模型
``PaperTradeReviewRecord`` 附带 agent_key（落库时注入，读取按 Agent 过滤）。

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
from pydantic import BaseModel, field_validator
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.core.prompt_loader import get_prompt_loader
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.core.locking import GENERATION_LOCK_TTL_SECONDS, redis_lock
from app.models.market_trade_calendar import MarketTradeCalendar
from app.models.paper_trade import (
    PaperTradeCashSnapshot,
    PaperTradeExecution,
    PaperTradeOrder,
    TradingAgent,
)
from app.models.stock import StockBasic
from app.repositories.review import ai_analysis_repository
from app.services.market.trade_calendar_service import NonTradingDayError
from app.services.review.market_review_service import ReviewInputDataNotReadyError

logger = structlog.get_logger(__name__)

REVIEW_SKILL_ID = "paper-trade-review"
ReviewPeriod = Literal["day", "week", "month"]
#: Literal 在运行时不可迭代，白名单单独维护（API 入参校验用）
REVIEW_PERIODS: tuple[str, ...] = ("day", "week", "month")

_PROMPT_SCOPE = "agents"
_PROMPT_ID = "trading_review"


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


class PaperTradeReviewContent(BaseModel):
    """复盘 LLM 结构化输出契约（字段禁默认值，进 JSON Schema required）。"""

    period: ReviewPeriod
    trade_date: str
    overall: str
    trades: list[TradeVerdict]
    bias: str
    suggestion: str
    experiences: list[ReviewExperience]

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
) -> ReviewGenerateResult:
    """生成（或读取缓存的）指定 Agent 的模拟盘分层复盘。

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

    if not regenerate:
        cached = await _load_cached(session, input_hash)
        if cached:
            return ReviewGenerateResult(content=cached, cached=True)

    if not await _sync_landed(session, account.id, resolved):
        raise ReviewInputDataNotReadyError(
            f"{resolved.isoformat()} 盘后同步尚未落库，模拟盘复盘输入未就绪"
        )

    if not await _has_review_target(session, account.id, start, end):
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
                return ReviewGenerateResult(content=cached, cached=True)
            raise PaperTradeReviewLockedError(
                f"其他实例正在生成 {resolved.isoformat()} 的 {period} 复盘"
            )

        if not regenerate:
            cached = await _load_cached(session, input_hash)
            if cached:
                return ReviewGenerateResult(content=cached, cached=True)

        window_input = await _collect_window_input(session, account.id, start, end)
        content = await _run_llm(session, agent, period, resolved, window_input)
        content = _validate(content, {o["cl_ord_id"] for o in window_input["orders"]})
        record = PaperTradeReviewRecord(
            **content.model_dump(), agent_key=agent.agent_key
        )

        await _persist(session, input_hash=input_hash, content=record)
        return ReviewGenerateResult(content=record, cached=False)


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
) -> PaperTradeReviewContent:
    config = get_prompt_loader().load(_PROMPT_SCOPE, _PROMPT_ID)
    user_prompt = (
        f"{config.system_prompt}\n\n"
        f"## 复盘人设（注册表行，D27）\n"
        f"- 你是{agent.name}（{agent.tagline}）；策略风格：{agent.style_desc}"
        f"——{agent.strategy_desc}\n"
        f"- 以该人设的视角与风格生成分层复盘结论\n\n"
        f"## 复盘任务\n"
        f"- 周期 period：{period}\n"
        f"- 基准交易日 trade_date：{trade_date.isoformat()}（输出字段须原样带回）\n\n"
        f"## 复盘输入数据（JSON，来源为 agent 账户本地委托/成交/资金快照）\n"
        f"{json.dumps(window_input, ensure_ascii=False, default=str)}"
    )
    from app.agent.runtime.structured import run_structured

    return await run_structured(
        session,
        result_type=PaperTradeReviewContent,
        user_prompt=user_prompt,
        config_id=agent.llm_config_id,
    )


def _validate(
    content: PaperTradeReviewContent, valid_cl_ord_ids: set[str]
) -> PaperTradeReviewContent:
    """后置校验：trades.cl_ord_id 必须来自窗口内真实委托（剔除幻觉行）。"""
    trades = [t for t in content.trades if t.cl_ord_id in valid_cl_ord_ids]
    return content.model_copy(update={"trades": trades})


async def _persist(session: AsyncSession, *, input_hash: str, content: Any) -> None:
    await ai_analysis_repository.insert_result(
        session,
        skill_id=REVIEW_SKILL_ID,
        input_hash=input_hash,
        prompt_id=REVIEW_SKILL_ID,
        model=None,
        structured=content.model_dump(mode="json"),
        latency_ms=0,
        status="success",
    )
    await session.commit()


async def _next_trading_day(session: AsyncSession, day: date) -> date | None:
    row = await session.scalar(
        select(MarketTradeCalendar.calendar_date)
        .where(
            MarketTradeCalendar.calendar_date > day,
            MarketTradeCalendar.is_trading.is_(True),
        )
        .order_by(MarketTradeCalendar.calendar_date.asc())
        .limit(1)
    )
    return row


async def is_last_trading_day_of_week(session: AsyncSession, day: date) -> bool:
    """day 之后最近的交易日是否已跨入下一周（ISO 周）——周五遇休市时周四即为周期末。"""
    nxt = await _next_trading_day(session, day)
    return nxt is None or nxt.isocalendar()[:2] != day.isocalendar()[:2]


async def is_last_trading_day_of_month(session: AsyncSession, day: date) -> bool:
    """day 之后最近的交易日是否已跨入下一月。"""
    nxt = await _next_trading_day(session, day)
    return nxt is None or (nxt.year, nxt.month) != (day.year, day.month)
