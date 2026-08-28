"""AI 大盘综述生成器：上下文组装、LLM 生成、缓存持久化。

生成结果按 (skill_id, input_hash) 缓存在 ai_analysis_result 表作为共享 base；
生成逻辑统一加 Redis 分布式锁，避免多租户场景下重复调用 LLM。
"""

import hashlib
from datetime import date, datetime, timezone
from typing import Any

import structlog
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.core.prompt_loader import PromptConfig, PromptLoader, PromptSection
from app.agent.core.prompt_renderer import PromptRenderer
from app.core.config import get_settings
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.core.locking import redis_lock
from app.repositories.review import (
    ai_analysis_repository,
    user_market_review_repository,
)
from app.schemas.market import MarketReviewResponse
from app.services.common.formatters import format_amount
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


class MarketReviewContent(BaseModel):
    """LLM 结构化输出：分区 key -> Markdown 内容。"""

    sections: dict[str, str]


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


def render_section_instructions(sections: list[PromptSection]) -> str:
    lines = ["请输出以下分区（以分区 key 为字段名）："]
    for index, section in enumerate(sections, start=1):
        requirements = section.requirements.strip()
        lines.append(f"{index}. {section.key}（{section.title}）：{requirements}")
    return "\n".join(lines)


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
    """
    # 懒加载：同层 service 导入会在 services/__init__ 初始化时触发与 app.agent.runtime 的循环导入
    from app.services.market import (
        index_quotation_service,
        index_technical_service,
        limit_pool_service,
        market_stats_service,
        sector_service,
    )

    if trade_date is not None:
        await assert_trading_day(session, trade_date)
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

        indices = await index_quotation_service.get_index_quotes(session, resolved_date)
        limit_up = await limit_pool_service.get_limit_up(session, resolved_date)
        sectors = await sector_service.get_sector_overview(session, resolved_date)
        technical_context = await index_technical_service.build_technical_context(
            session, resolved_date
        )

        index_context = "；".join(
            f"{item.name} {item.price:.2f}（{item.change_pct:+.2f}%）" for item in indices
        )
        ladder_context = (
            "；".join(
                f"{item.stock_name}（{item.stock_code}）{item.consecutive_boards}板"
                f" [{item.industry or '未分类'}]"
                for item in limit_up.ladder[:10]
            )
            or "当日无连板个股"
        )
        inflow_context = "；".join(
            f"{item.sector_name} {format_amount(item.main_net_inflow)}"
            for item in sectors.top_inflow
        ) or "无数据"
        outflow_context = "；".join(
            f"{item.sector_name} {format_amount(item.main_net_inflow)}"
            for item in sectors.top_outflow
        ) or "无数据"
        leading_context = "；".join(
            f"{item.sector_name}（{item.change_pct:+.2f}%，涨停 {item.limit_up_count} 家）"
            for item in sectors.leading
            if item.change_pct is not None
        ) or "无数据"

        if inflow_context == "无数据" and outflow_context == "无数据" and leading_context == "无数据":
            raise ReviewInputDataNotReadyError(
                "板块资金与领涨板块数据尚未就绪，无法生成资金面分析"
            )

        user_prompt = PromptRenderer.render(
            prompt_config.user_prompt_template,
            trade_date=resolved_date.isoformat(),
            index_context=index_context,
            technical_context=technical_context,
            amount_text=format_amount(stats.amount),
            up_count=stats.up_count if stats.up_count is not None else "未知",
            down_count=stats.down_count if stats.down_count is not None else "未知",
            flat_count=stats.flat_count if stats.flat_count is not None else "未知",
            limit_up_count=stats.limit_up_count,
            limit_down_count=stats.limit_down_count,
            emotion_score=(
                stats.emotion_score if stats.emotion_score is not None else "未知"
            ),
            emotion_label=stats.emotion_label or "未知",
            limit_up_ratio=(
                stats.limit_up_ratio if stats.limit_up_ratio is not None else "未知"
            ),
            continuous_rate_text=(
                f"{stats.continuous_rate * 100:.1f}%"
                if stats.continuous_rate is not None
                else "未知"
            ),
            broken_rate_text=(
                f"{stats.broken_rate * 100:.1f}%"
                if stats.broken_rate is not None
                else "未知"
            ),
            ladder_context=ladder_context,
            inflow_context=inflow_context,
            outflow_context=outflow_context,
            leading_context=leading_context,
            section_instructions=render_section_instructions(sections),
        )

        from app.agent.runtime import run_structured_agent_with_metrics

        output, latency_ms, model_name = await run_structured_agent_with_metrics(
            session,
            prompt_config=prompt_config,
            user_prompt=user_prompt,
            result_type=MarketReviewContent,
        )

        declared_keys = {section.key for section in sections}
        missing = declared_keys - output.sections.keys()
        if missing:
            logger.warning(
                "market_review_section_missing",
                trade_date=resolved_date.isoformat(),
                missing=sorted(missing),
            )
        contents = {
            section.key: output.sections.get(section.key, "") for section in sections
        }

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
