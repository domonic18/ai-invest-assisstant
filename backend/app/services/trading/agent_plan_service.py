"""交易 Agent 每日选股与交易计划生成服务（批次 7，plan §10.2）。

19:00 定时生成：输入 = 当日复盘解读（market-daily-review，18:35 后就绪——
缺失即 ``ReviewInputDataNotReadyError`` 退避重试）+ 涨停归因 + 异动归因 +
agent 账户本地持仓 + 人工移出清单 + agent 记忆（温程方法论种子 + 复盘沉淀，
``agent_memory`` active 条目全量注入）。
LLM 单轮结构化输出字段全 required（禁默认值铁律）；按
(skill_id, input_hash=账户+交易日) 缓存 ``ai_analysis_result``，redis 锁防
重入。落库 upsert 两表并同步 agent 自选分组（选入加入 / 未续选 agent 剔除 /
人工移出全局生效不重复选入）。
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

import structlog
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.core.prompt_loader import get_prompt_loader
from app.core.exceptions import ConflictError
from app.core.locking import GENERATION_LOCK_TTL_SECONDS, redis_lock
from app.models.agent_trading import AgentStockSelection, AgentTradePlan
from app.models.market_anomaly import StockAnomaly
from app.models.paper_trade import PaperTradeExecution
from app.models.stock import StockBasic
from app.repositories.review import ai_analysis_repository
from app.services.review.market_review_generator import (
    SKILL_ID as MARKET_REVIEW_SKILL_ID,
)
from app.services.review.market_review_service import ReviewInputDataNotReadyError
from app.services.trading import account_service
from app.services.trading.agent_config import get_config_row

logger = structlog.get_logger(__name__)

PLAN_SKILL_ID = "agent-daily-plan"

_PROMPT_SCOPE = "agents"
_PROMPT_ID = "agent_daily_plan"

#: 异动归因注入 prompt 的条数上限（按 strength 降序）
_ANOMALY_TOP_N = 10
#: 人工移出清单回看窗口（天）——超过后允许重新候选
_MANUAL_REMOVED_WINDOW_DAYS = 14
#: agent 记忆注入条数上限
_MEMORY_TOP_N = 20


class PlanGenerationLockedError(ConflictError):
    """其他实例正在生成同日交易计划。"""

    default_message = "交易计划正在生成中，请稍后重试"


class PlanSelectionItem(BaseModel):
    """选股条目（字段禁默认值——LLM 必须对每项显式表态）。"""

    stock_code: str
    reason: str
    confidence: float | None


class PlanTradePlanItem(BaseModel):
    """交易计划条目（buy 必填买点区间；sell 必填止盈；两类均必填止损）。"""

    stock_code: str
    plan_type: Literal["buy", "sell"]
    strategy: str
    buy_zone_low: float | None
    buy_zone_high: float | None
    target_price: float | None
    stop_loss: float
    position_pct: float
    basis: str

    @field_validator("plan_type", mode="before")
    @classmethod
    def _normalize_plan_type(cls, value: Any) -> Any:
        """边界归一：中文计划类型（买入/卖出）映射回白名单字面量。"""
        if isinstance(value, str):
            mapping = {"买入": "buy", "开仓": "buy", "卖出": "sell", "清仓": "sell"}
            return mapping.get(value.strip(), value)
        return value


class AgentDailyPlanContent(BaseModel):
    """每日计划结构化输出契约（ai_analysis_result.structured_output 形状）。"""

    trade_date: str
    selections: list[PlanSelectionItem]
    plans: list[PlanTradePlanItem]


@dataclass(slots=True)
class PlanGenerateResult:
    """生成结果：内容 + 是否缓存命中 + 剔除明细（任务 metadata 用）。"""

    content: AgentDailyPlanContent
    cached: bool
    dropped_codes: list[str]


def _input_hash(account_id: int, trade_date: date) -> str:
    raw = f"{PLAN_SKILL_ID}:{account_id}:{trade_date.isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def _load_cached(
    session: AsyncSession, input_hash: str
) -> AgentDailyPlanContent | None:
    row = await ai_analysis_repository.load_latest_success(
        session, skill_id=PLAN_SKILL_ID, input_hash=input_hash
    )
    if row is None or not row.structured_output:
        return None
    return AgentDailyPlanContent.model_validate(row.structured_output)


async def _market_review_sections(
    session: AsyncSession, trade_date: date
) -> dict[str, Any]:
    """当日复盘解读全文（就绪预检：缺失即输入未就绪，18:35 任务生成）。"""
    row = await ai_analysis_repository.load_latest_success(
        session, skill_id=MARKET_REVIEW_SKILL_ID, trade_date=trade_date
    )
    if row is None or not row.structured_output:
        raise ReviewInputDataNotReadyError(
            f"{trade_date.isoformat()} 当日复盘解读尚未生成，每日计划输入未就绪"
        )
    return row.structured_output


async def _limit_up_attribution(
    session: AsyncSession, trade_date: date
) -> dict[str, Any] | None:
    from app.services.review import limit_up_ai_service

    content = await limit_up_ai_service.get_cached_attribution(session, trade_date)
    return None if content is None else content.model_dump()


async def _stock_anomalies(
    session: AsyncSession, trade_date: date
) -> list[dict[str, Any]]:
    rows = (
        (
            await session.execute(
                select(StockAnomaly)
                .where(StockAnomaly.trade_date == trade_date)
                .order_by(StockAnomaly.strength.desc())
                .limit(_ANOMALY_TOP_N)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "stock_code": r.stock_code,
            "stock_name": r.stock_name,
            "change_pct": float(r.change_pct) if r.change_pct is not None else None,
            "anomaly_types": r.anomaly_types,
            "attribution_category": r.attribution_category,
            "attribution_summary": r.attribution_summary,
        }
        for r in rows
    ]


async def _manual_removed_codes(session: AsyncSession, trade_date: date) -> list[str]:
    """近期人工移出清单（全局生效：prompt 声明禁止选入 + 服务层兜底过滤）。"""
    since = trade_date.toordinal() - _MANUAL_REMOVED_WINDOW_DAYS
    rows = await session.execute(
        select(AgentStockSelection.stock_code)
        .where(
            AgentStockSelection.removed_reason == "manual",
            AgentStockSelection.trade_date >= date.fromordinal(since),
        )
        .distinct()
    )
    return [code for code in rows.scalars().all()]


async def _local_positions(session: AsyncSession, account_id: int) -> list[dict[str, Any]]:
    """agent 账户当前持仓（本地成交聚合，不依赖柜台）：净持有 > 0 的标的。"""
    rows = (
        (
            await session.execute(
                select(PaperTradeExecution)
                .where(PaperTradeExecution.paper_trade_account_id == account_id)
                .order_by(PaperTradeExecution.trade_date.asc())
            )
        )
        .scalars()
        .all()
    )
    agg: dict[str, dict[str, float]] = {}
    for row in rows:
        code = row.symbol.split(".")[-1]
        volume = float(row.volume or 0)
        price = float(row.price or 0)
        entry = agg.setdefault(code, {"volume": 0.0, "cost": 0.0})
        if row.side == 1:
            entry["volume"] += volume
            entry["cost"] += volume * price
        elif row.side == 2:
            entry["volume"] -= volume
    return [
        {
            "stock_code": code,
            "volume": int(item["volume"]),
            "avg_cost": round(item["cost"] / item["volume"], 4)
            if item["volume"] > 0
            else None,
        }
        for code, item in sorted(agg.items())
        if item["volume"] > 0
    ]


async def _active_memories(session: AsyncSession) -> list[dict[str, Any]]:
    """agent 记忆 active 条目（方法论纪律种子 + 复盘沉淀，停用条目不注入）。"""
    from sqlalchemy import text

    # SAVEPOINT 隔离：表缺失等失败只回滚到保存点，避免外层事务进入 aborted 态
    try:
        async with session.begin_nested():
            rows = await session.execute(
                text(
                    "SELECT title, body, mem_type FROM agent_memory "
                    "WHERE status = 'active' ORDER BY updated_at DESC LIMIT :n"
                ),
                {"n": _MEMORY_TOP_N},
            )
            items = [
                {"title": r.title, "body": r.body, "mem_type": r.mem_type}
                for r in rows.mappings().all()
            ]
    except (OperationalError, ProgrammingError):
        # 批次 9 建 agent_memory 前表不存在（asyncpg UndefinedTable → ProgrammingError）；
        # 记忆注入是可选增强，任何取数失败都降级为空集，不阻塞每日计划。
        return []
    return items


async def _collect_plan_input(
    session: AsyncSession, account_id: int, trade_date: date
) -> tuple[dict[str, Any], list[str]]:
    """组装 LLM 输入，返回 (输入 dict, 人工移出代码清单)。"""
    review = await _market_review_sections(session, trade_date)
    manual_removed = await _manual_removed_codes(session, trade_date)
    return (
        {
            "trade_date": trade_date.isoformat(),
            "market_review": review.get("sections") or review,
            "limit_up_attribution": await _limit_up_attribution(session, trade_date),
            "stock_anomalies": await _stock_anomalies(session, trade_date),
            "positions": await _local_positions(session, account_id),
            "manual_removed_codes": manual_removed,
            "memories": await _active_memories(session),
        },
        manual_removed,
    )


async def _run_llm(
    session: AsyncSession, trade_date: date, plan_input: dict[str, Any]
) -> AgentDailyPlanContent:
    config = get_prompt_loader().load(_PROMPT_SCOPE, _PROMPT_ID)
    config_row = await get_config_row(session)
    user_prompt = (
        f"{config.system_prompt}\n\n"
        f"## 计划任务\n"
        f"- 基准交易日 trade_date：{trade_date.isoformat()}（输出字段须原样带回）\n\n"
        f"## 计划输入数据（JSON）\n"
        f"{json.dumps(plan_input, ensure_ascii=False, default=str)}"
    )
    from app.agent.runtime.structured import run_structured

    return await run_structured(
        session,
        result_type=AgentDailyPlanContent,
        user_prompt=user_prompt,
        config_id=config_row.llm_config_id,
    )


async def _validate_codes(
    session: AsyncSession, content: AgentDailyPlanContent, manual_removed: list[str]
) -> tuple[AgentDailyPlanContent, list[str]]:
    """后置校验：剔除 stock_basic 不存在的幻觉代码与人工移出代码。"""
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
    content = content.model_copy(
        update={
            "selections": [s for s in content.selections if s.stock_code in keep],
            "plans": [p for p in content.plans if p.stock_code in keep],
        }
    )
    return content, dropped


async def _ensure_agent_group(session: AsyncSession) -> Any:
    """平台级 agent 自选分组单例（owner_type='agent'，user_id=NULL）。"""
    from app.models.watchlist import UserWatchlistGroup

    row = await session.scalar(
        select(UserWatchlistGroup).where(UserWatchlistGroup.owner_type == "agent")
    )
    if row is not None:
        return row
    row = UserWatchlistGroup(
        user_id=None,
        owner_type="agent",
        name="交易 Agent",
        sort_order=999,
        is_default=False,
        ai_review_enabled=False,
    )
    session.add(row)
    await session.flush()
    return row


async def _persist(
    session: AsyncSession,
    *,
    trade_date: date,
    content: AgentDailyPlanContent,
    source_result_id: int,
) -> None:
    """upsert 选股/计划两表 + agent 分组同步（人工移出不覆盖）。"""
    await _ensure_agent_group(session)

    selection_ids: dict[str, int] = {}
    for item in content.selections:
        row = await session.scalar(
            select(AgentStockSelection).where(
                AgentStockSelection.trade_date == trade_date,
                AgentStockSelection.stock_code == item.stock_code,
            )
        )
        if row is None:
            row = AgentStockSelection(
                trade_date=trade_date,
                stock_code=item.stock_code,
                reason=item.reason,
                status="active",
            )
            session.add(row)
        else:
            row.reason = item.reason
            row.status = row.status if row.status == "removed" else "active"
            if row.status == "active":
                row.removed_at = None
                row.removed_reason = None
        row.confidence = (
            None if item.confidence is None else Decimal(str(round(item.confidence, 4)))
        )
        row.source_result_id = source_result_id
        await session.flush()
        selection_ids[item.stock_code] = row.id

    # 未续选的既往 active 选股 → agent 剔除（人工移出行不覆盖）
    stale = (
        (
            await session.execute(
                select(AgentStockSelection).where(
                    AgentStockSelection.status == "active",
                    AgentStockSelection.trade_date < trade_date,
                )
            )
        )
        .scalars()
        .all()
    )
    today_codes = {s.stock_code for s in content.selections}
    from app.core.clock import utc_now

    for row in stale:
        if row.stock_code in today_codes:
            continue
        row.status = "removed"
        row.removed_at = utc_now()
        row.removed_reason = "agent"

    for plan_item in content.plans:
        plan_row = await session.scalar(
            select(AgentTradePlan).where(
                AgentTradePlan.plan_date == trade_date,
                AgentTradePlan.stock_code == plan_item.stock_code,
                AgentTradePlan.plan_type == plan_item.plan_type,
            )
        )
        if plan_row is None:
            plan_row = AgentTradePlan(
                plan_date=trade_date,
                stock_code=plan_item.stock_code,
                plan_type=plan_item.plan_type,
                status="active",
            )
            session.add(plan_row)
        plan_row.strategy = plan_item.strategy
        plan_row.buy_zone_low = (
            None if plan_item.buy_zone_low is None else Decimal(str(plan_item.buy_zone_low))
        )
        plan_row.buy_zone_high = (
            None if plan_item.buy_zone_high is None else Decimal(str(plan_item.buy_zone_high))
        )
        plan_row.target_price = (
            None if plan_item.target_price is None else Decimal(str(plan_item.target_price))
        )
        plan_row.stop_loss = Decimal(str(plan_item.stop_loss))
        plan_row.position_pct = Decimal(str(plan_item.position_pct))
        plan_row.basis = plan_item.basis
        plan_row.raw = content.model_dump(mode="json")
        # 人工 cancelled / 已触发的状态机字段不回改；当日未触发的 expired 可被重新生成复活
        if plan_row.status == "expired":
            plan_row.status = "active"
        if plan_item.plan_type == "buy":
            plan_row.selection_id = (
                selection_ids.get(plan_item.stock_code) or plan_row.selection_id
            )
    await session.commit()


async def generate_daily_plan(
    session: AsyncSession,
    *,
    trade_date: date | None = None,
    regenerate: bool = False,
) -> PlanGenerateResult:
    """生成（或读取缓存的）当日选股与交易计划。

    Raises:
        NonTradingDayError: 指定日期不是交易日
        AgentAccountNotDesignatedError: 未指定 agent 专属账户
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
    account = await account_service.resolve_agent_account(session)
    input_hash = _input_hash(account.id, resolved)

    if not regenerate:
        cached = await _load_cached(session, input_hash)
        if cached:
            return PlanGenerateResult(
                content=cached, cached=True, dropped_codes=[]
            )

    # 输入组装（内含就绪预检：复盘解读缺失即抛未就绪）
    plan_input, manual_removed = await _collect_plan_input(session, account.id, resolved)

    async with redis_lock(
        f"{PLAN_SKILL_ID}:{account.id}:{resolved.isoformat()}",
        ttl=GENERATION_LOCK_TTL_SECONDS,
    ) as acquired:
        if not acquired:
            cached = await _load_cached(session, input_hash)
            if cached:
                return PlanGenerateResult(content=cached, cached=True, dropped_codes=[])
            raise PlanGenerationLockedError(
                f"其他实例正在生成 {resolved.isoformat()} 的每日计划"
            )

        if not regenerate:
            cached = await _load_cached(session, input_hash)
            if cached:
                return PlanGenerateResult(content=cached, cached=True, dropped_codes=[])

        content = await _run_llm(session, resolved, plan_input)
        content, dropped = await _validate_codes(session, content, manual_removed)
        cache_row_id = await _persist_cache_row(session, input_hash=input_hash, content=content)
        await _persist(
            session,
            trade_date=resolved,
            content=content,
            source_result_id=cache_row_id,
        )
        if dropped:
            logger.warning(
                "agent_daily_plan_codes_dropped", codes=dropped, trade_date=resolved.isoformat()
            )
        return PlanGenerateResult(content=content, cached=False, dropped_codes=dropped)


async def _persist_cache_row(
    session: AsyncSession, *, input_hash: str, content: AgentDailyPlanContent
) -> int:
    return await ai_analysis_repository.insert_result(
        session,
        skill_id=PLAN_SKILL_ID,
        input_hash=input_hash,
        prompt_id=PLAN_SKILL_ID,
        model=None,
        structured=content.model_dump(mode="json"),
        latency_ms=0,
        status="success",
    )
