"""AI 大盘综述生成器：deepagents 工具循环生成、缓存持久化。

生成结果按 (skill_id, input_hash) 缓存在 ai_analysis_result 表作为共享 base；
生成逻辑统一加 Redis 分布式锁，避免多租户场景下重复调用 LLM。生成内核为
``app.agent.skills.market_review_agent.run_skill``（数据取数由 SKILL 工具循环
完成），就绪预检保留以支撑 celery 任务的退避重试语义。
"""

import hashlib
from datetime import date, datetime, timezone
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.core.prompt_loader import PromptConfig, PromptLoader, PromptSection
from app.core.config import get_settings
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.core.locking import redis_lock
from app.repositories.review import (
    ai_analysis_repository,
    user_market_review_repository,
)
from app.schemas.market import MarketReviewResponse
from app.services.review.market_review_formatter import (
    BaseReview,
    build_response,
)

logger = structlog.get_logger(__name__)

SKILL_ID = "market-daily-review"


class NonTradingDayError(BadRequestError):
    """指定日期不是交易日，每日复盘只对交易日有效。"""


class ReviewNotFoundError(NotFoundError):
    """指定交易日不存在已生成的 AI 复盘。"""


class ReviewGenerationLockedError(ConflictError):
    """其他实例正在生成同交易日的大盘综述。"""


class ReviewInputDataNotReadyError(BadRequestError):
    """生成所需输入数据（板块资金、涨停池等）尚未就绪。"""

    default_message = "当日行情数据尚未采集完成，请稍后重试"


def load_prompt_config() -> PromptConfig:
    config = PromptLoader(get_settings().prompts_dir).load("skills", SKILL_ID)
    if not config.sections:
        raise ValueError(f"{SKILL_ID} prompt 未声明任何 sections 分区")
    return config


def input_hash(trade_date: date, sections: list[PromptSection]) -> str:
    """缓存键纳入分区键集合：新增/调整分区后旧缓存自动失效。"""
    keys = ",".join(section.key for section in sections)
    raw = f"{SKILL_ID}:{keys}:{trade_date.isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _hash_for(session_date: date, sections: list[PromptSection]) -> str:
    return input_hash(session_date, sections)


async def _load_base_review(
    session: AsyncSession, trade_date: date, sections: list[PromptSection]
) -> BaseReview | None:
    """读取共享 base 记录。"""
    row = await ai_analysis_repository.load_latest_success(
        session,
        skill_id=SKILL_ID,
        input_hash=_hash_for(trade_date, sections),
    )
    if row is None or not row.structured_output:
        return None
    output = row.structured_output
    return BaseReview(
        id=row.id,
        response=build_response(
            trade_date=date.fromisoformat(output["trade_date"]),
            contents=output.get("sections") or {},
            sections=sections,
            model=row.model,
            generated_at=row.created_at,
            cached=True,
            edited=False,
        ),
    )


async def _load_user_edit_row(
    session: AsyncSession, user_id: int, trade_date: date
) -> Any | None:
    """读取用户编辑副本原始行（sections JSONB，未编辑的分区不在其中）。"""
    return await user_market_review_repository.find(
        session, user_id=user_id, trade_date=trade_date
    )


async def assert_trading_day(session: AsyncSession, day: date) -> None:
    from app.services.market import trade_calendar_service

    if not await trade_calendar_service.is_trading_day(session, day):
        raise NonTradingDayError(f"{day.isoformat()} 不是交易日，每日复盘只对交易日有效")


async def _persist(
    session: AsyncSession,
    input_hash_str: str,
    model: str,
    contents: dict[str, str],
    trade_date: date,
    latency_ms: int,
) -> None:
    structured: dict[str, Any] = {
        "trade_date": trade_date.isoformat(),
        "sections": contents,
    }
    await ai_analysis_repository.insert_result(
        session,
        skill_id=SKILL_ID,
        input_hash=input_hash_str,
        prompt_id=SKILL_ID,
        model=model,
        structured=structured,
        latency_ms=latency_ms,
    )
    await session.commit()


async def persist_market_review_result(
    session: AsyncSession,
    *,
    trade_date: date,
    contents: dict[str, str],
    model: str,
    latency_ms: int = 0,
) -> MarketReviewResponse:
    """将助手/skill 产出的五分区复盘落库（ai_analysis_result），返回响应。

    Args:
        latency_ms: 生成耗时（毫秒）；助手对话路径由工具层计时传入，
            手动编辑路径缺省为 0。

    Raises:
        ValueError: sections 缺少 prompt 声明的分区键或内容为空。
    """
    sections = load_prompt_config().sections
    missing = [s.key for s in sections if not (contents.get(s.key) or "").strip()]
    if missing:
        expected = ", ".join(s.key for s in sections)
        raise ValueError(
            f"sections 缺少必填分区：{', '.join(missing)}；期望键集：{expected}"
        )

    filtered = {s.key: contents[s.key] for s in sections}
    await _persist(
        session,
        _hash_for(trade_date, sections),
        model,
        filtered,
        trade_date,
        latency_ms,
    )
    return build_response(
        trade_date=trade_date,
        contents=filtered,
        sections=sections,
        model=model,
        generated_at=datetime.now(timezone.utc),
        cached=False,
        edited=False,
    )


async def generate_market_review(
    session: AsyncSession,
    trade_date: date | None = None,
    regenerate: bool = False,
    blocking: bool = False,
    blocking_timeout: float = 30,
) -> MarketReviewResponse:
    """生成（或读取缓存的）AI 大盘综述共享 base。

    Args:
        session: 数据库会话。
        trade_date: 指定交易日；None 时取最近交易日。
        regenerate: 是否强制重新生成。
        blocking: 获取 Redis 锁时是否阻塞等待。
        blocking_timeout: 阻塞等待锁的最大秒数。

    Returns:
        MarketReviewResponse，cached=True 表示命中已有缓存。

    Raises:
        NonTradingDayError: 指定日期不是交易日。
        ReviewGenerationLockedError: 非阻塞模式下锁被占用且缓存不存在。
        ReviewInputDataNotReadyError: 板块资金等输入数据尚未就绪。
    """
    if trade_date is not None:
        await assert_trading_day(session, trade_date)

    from app.services.market import market_stats_service, sector_service

    stats = await market_stats_service.get_market_stats(session, trade_date)
    resolved_date = stats.trade_date

    prompt_config = load_prompt_config()
    sections = prompt_config.sections
    current_hash = _hash_for(resolved_date, sections)

    if not regenerate:
        cached = await _load_base_review(session, resolved_date, sections)
        if cached is not None:
            return cached.response

    async with redis_lock(
        f"market-daily-review:{resolved_date}",
        ttl=300,
        blocking=blocking,
        blocking_timeout=blocking_timeout,
    ) as acquired:
        if not acquired:
            cached = await _load_base_review(session, resolved_date, sections)
            if cached is not None:
                return cached.response
            raise ReviewGenerationLockedError(
                f"其他实例正在生成 {resolved_date.isoformat()} 的大盘综述"
            )

        if not regenerate:
            cached = await _load_base_review(session, resolved_date, sections)
            if cached is not None:
                return cached.response

        # 就绪预检：板块资金数据未就绪时抛错，celery 任务依赖该异常做退避重试，
        # 同时避免在数据缺失时白烧 LLM token（具体取数由 SKILL 工具循环完成）
        sectors = await sector_service.get_sector_overview(session, resolved_date)
        has_flow = bool(sectors.top_inflow) or bool(sectors.top_outflow)
        has_leading = any(item.change_pct is not None for item in sectors.leading)
        if not (has_flow or has_leading):
            raise ReviewInputDataNotReadyError(
                "板块资金与领涨板块数据尚未就绪，无法生成资金面分析"
            )

        from app.agent.skills.market_review_agent import run_skill

        contents, model_name, latency_ms = await run_skill(
            session, trade_date=resolved_date, prompt_config=prompt_config
        )

        await _persist(
            session, current_hash, model_name, contents, resolved_date, latency_ms
        )

        return build_response(
            trade_date=resolved_date,
            contents=contents,
            sections=sections,
            model=model_name,
            generated_at=datetime.now(timezone.utc),
            cached=False,
            edited=False,
        )
