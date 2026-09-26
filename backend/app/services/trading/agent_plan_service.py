"""交易 Agent 每日选股与交易计划生成服务（批次 7，plan §10.2 编排层）。

19:00 定时生成：输入 = 当日复盘解读（18:35 后就绪，缺失即退避重试）+
涨停归因 + 异动归因 + agent 持仓 + 人工移出清单 + 方法论基座（KB 直读）+
经验记忆（``agent_plan_input.collect_plan_input`` 组装）→ LLM 单轮结构化
输出（契约见 ``agent_plan_schemas``）→ 幻觉/人工移出代码后置校验 → 缓存行
+ 两表 upsert（``agent_plan_persist``）。按 (skill_id, input_hash=账户+
交易日) 缓存 ``ai_analysis_result``，redis 锁防重入。
"""

import hashlib
import json
from datetime import date

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.core.prompt_loader import get_prompt_loader
from app.core.exceptions import ConflictError
from app.core.locking import GENERATION_LOCK_TTL_SECONDS, redis_lock
from app.models.stock import StockBasic
from app.repositories.review import ai_analysis_repository
from app.services.trading import account_service, agent_plan_input, agent_plan_persist
from app.services.trading.agent_config import get_config_row
from app.services.trading.agent_plan_schemas import (
    AgentDailyPlanContent,
    PlanGenerateResult,
)

logger = structlog.get_logger(__name__)

PLAN_SKILL_ID = "agent-daily-plan"

_PROMPT_SCOPE = "agents"
_PROMPT_ID = "agent_daily_plan"


class PlanGenerationLockedError(ConflictError):
    """其他实例正在生成同日交易计划。"""

    default_message = "交易计划正在生成中，请稍后重试"


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


async def _run_llm(
    session: AsyncSession, trade_date: date, plan_input: dict
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
    plan_input, manual_removed = await agent_plan_input.collect_plan_input(
        session, account.id, resolved
    )

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
        cache_row_id = await agent_plan_persist.persist_cache_row(
            session, skill_id=PLAN_SKILL_ID, input_hash=input_hash, content=content
        )
        await agent_plan_persist.persist_plan(
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
