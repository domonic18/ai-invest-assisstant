"""AI 大盘综述（LLM 复盘报告）服务。

生成结果按 (skill_id, input_hash) 缓存在 ai_analysis_result 表作为共享 base；
用户编辑副本保存在 user_market_review 表（sections JSONB 列），读取时按分区 overlay。
内容分区由 prompt YAML 的 sections 声明驱动：新增分析维度只需在
skills/market-daily-review.yaml 追加一条 section，无需改动本模块、API 或前端。
生成逻辑统一加 Redis 分布式锁，避免多租户场景下重复调用 LLM。
"""

import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import structlog
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.core.prompt_loader import PromptConfig, PromptLoader, PromptSection
from app.agent.core.prompt_renderer import PromptRenderer
from app.agent.runtime import run_structured_agent_with_metrics
from app.core.config import get_settings
from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    UnprocessableEntityError,
)
from app.core.locking import redis_lock
from app.models.user_market_review import UserMarketReview
from app.repositories import (
    ai_analysis_repository,
    user_market_review_repository,
)
from app.schemas.market import MarketReviewResponse, MarketReviewSection
from app.services import (
    index_quotation_service,
    index_technical_service,
    limit_pool_service,
    market_stats_service,
    sector_service,
    trade_calendar_service,
)

logger = structlog.get_logger(__name__)

SKILL_ID = "market-daily-review"


class ReviewNotFoundError(NotFoundError):
    """指定交易日不存在已生成的 AI 复盘。"""


class NonTradingDayError(BadRequestError):
    """指定日期不是交易日，每日复盘只对交易日有效。"""


class ReviewGenerationLockedError(ConflictError):
    """其他实例正在生成同交易日的大盘综述。"""


class UnknownSectionError(UnprocessableEntityError):
    """编辑的分区未在 prompt YAML 的 sections 中声明。"""


class MarketReviewContent(BaseModel):
    """LLM 结构化输出：分区 key -> Markdown 内容。"""

    sections: dict[str, str]


@dataclass
class _BaseReview:
    """共享 base 记录（含数据库主键，用于用户编辑副本关联）。"""

    id: int
    response: MarketReviewResponse


def _load_prompt_config() -> PromptConfig:
    config = PromptLoader(get_settings().prompts_dir).load("skills", SKILL_ID)
    if not config.sections:
        raise ValueError(f"{SKILL_ID} prompt 未声明任何 sections 分区")
    return config


def _input_hash(trade_date: date, sections: list[PromptSection]) -> str:
    """缓存键纳入分区键集合：新增/调整分区后旧缓存自动失效。"""
    keys = ",".join(section.key for section in sections)
    raw = f"{SKILL_ID}:{keys}:{trade_date.isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _build_response(
    trade_date: date,
    contents: dict[str, str],
    sections: list[PromptSection],
    model: str | None,
    generated_at: datetime,
    cached: bool,
    edited: bool,
) -> MarketReviewResponse:
    """按 YAML 声明的分区顺序组装响应（未声明的内容键丢弃，缺失分区补空串）。"""
    return MarketReviewResponse(
        trade_date=trade_date,
        sections=[
            MarketReviewSection(
                key=section.key,
                title=section.title,
                content=contents.get(section.key, ""),
            )
            for section in sections
        ],
        model=model,
        generated_at=generated_at,
        cached=cached,
        edited=edited,
    )


def _format_amount(amount: float | None) -> str:
    if amount is None:
        return "未知"
    if amount >= 1e12:
        return f"{amount / 1e12:.2f} 万亿元"
    return f"{amount / 1e8:.0f} 亿元"


async def _load_base_review(
    session: AsyncSession, trade_date: date, sections: list[PromptSection]
) -> _BaseReview | None:
    """读取共享 base 记录。"""
    row = await ai_analysis_repository.load_latest_success(
        session,
        skill_id=SKILL_ID,
        input_hash=_input_hash(trade_date, sections),
    )
    if row is None or not row.structured_output:
        return None
    output = row.structured_output
    return _BaseReview(
        id=row.id,
        response=_build_response(
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
) -> UserMarketReview | None:
    """读取用户编辑副本原始行（sections JSONB，未编辑的分区不在其中）。"""
    return await user_market_review_repository.find(
        session, user_id=user_id, trade_date=trade_date
    )


async def _resolve_trade_date(
    session: AsyncSession, trade_date: date | None
) -> date:
    stats = await market_stats_service.get_market_stats(session, trade_date)
    return stats.trade_date


async def _assert_trading_day(session: AsyncSession, day: date) -> None:
    if not await trade_calendar_service.is_trading_day(session, day):
        raise NonTradingDayError(f"{day.isoformat()} 不是交易日，每日复盘只对交易日有效")


async def get_market_review(
    session: AsyncSession,
    user_id: int,
    trade_date: date | None = None,
) -> MarketReviewResponse | None:
    """读取用户视图的大盘综述：用户编辑版按分区 overlay 在共享 base 之上。

    只读，不触发 LLM 生成。
    """
    if trade_date is not None:
        await _assert_trading_day(session, trade_date)
    resolved_date = await _resolve_trade_date(session, trade_date)

    sections = _load_prompt_config().sections
    base = await _load_base_review(session, resolved_date, sections)
    user_row = await _load_user_edit_row(session, user_id, resolved_date)
    if user_row is None:
        return base.response if base is not None else None

    base_contents = (
        {item.key: item.content for item in base.response.sections}
        if base is not None
        else {}
    )
    user_sections: dict[str, str] = user_row.sections or {}
    merged = {
        section.key: user_sections.get(section.key, base_contents.get(section.key, ""))
        for section in sections
    }
    base_model = base.response.model if base is not None else None
    return _build_response(
        trade_date=resolved_date,
        contents=merged,
        sections=sections,
        model=user_row.model or base_model,
        generated_at=user_row.generated_at or user_row.created_at,
        cached=True,
        edited=True,
    )


async def update_market_review(
    session: AsyncSession,
    user_id: int,
    trade_date: date,
    section_key: str,
    content: str,
) -> MarketReviewResponse:
    """按分区保存用户编辑内容到个人账户（不影响共享 base）。

    其余分区沿用用户已有编辑，未曾编辑的分区从共享 base 拷贝补齐。
    """
    await _assert_trading_day(session, trade_date)

    sections = _load_prompt_config().sections
    if section_key not in {section.key for section in sections}:
        raise UnknownSectionError(f"未知的复盘分区：{section_key}")

    base = await _load_base_review(session, trade_date, sections)
    if base is None:
        raise ReviewNotFoundError(f"{trade_date.isoformat()} 尚未生成 AI 复盘")

    merged = {item.key: item.content for item in base.response.sections}
    existing = await _load_user_edit_row(session, user_id, trade_date)
    if existing is not None:
        merged.update(existing.sections or {})
    merged[section_key] = content

    await user_market_review_repository.upsert_sections(
        session,
        user_id=user_id,
        trade_date=trade_date,
        sections=merged,
        model=base.response.model,
        generated_at=base.response.generated_at,
        base_review_id=base.id,
    )
    await session.commit()

    return _build_response(
        trade_date=trade_date,
        contents=merged,
        sections=sections,
        model=base.response.model,
        generated_at=base.response.generated_at,
        cached=True,
        edited=True,
    )


async def _persist(
    session: AsyncSession,
    input_hash: str,
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
        input_hash=input_hash,
        prompt_id=SKILL_ID,
        model=model,
        structured=structured,
        latency_ms=latency_ms,
    )
    await session.commit()


def _render_section_instructions(sections: list[PromptSection]) -> str:
    lines = ["请输出以下分区（以分区 key 为字段名）："]
    for index, section in enumerate(sections, start=1):
        requirements = section.requirements.strip()
        lines.append(f"{index}. {section.key}（{section.title}）：{requirements}")
    return "\n".join(lines)


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
    if trade_date is not None:
        await _assert_trading_day(session, trade_date)
    stats = await market_stats_service.get_market_stats(session, trade_date)
    resolved_date = stats.trade_date

    prompt_config = _load_prompt_config()
    sections = prompt_config.sections
    input_hash = _input_hash(resolved_date, sections)

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
            f"{item.sector_name} {_format_amount(item.main_net_inflow)}"
            for item in sectors.top_inflow
        ) or "无数据"
        outflow_context = "；".join(
            f"{item.sector_name} {_format_amount(item.main_net_inflow)}"
            for item in sectors.top_outflow
        ) or "无数据"
        leading_context = "；".join(
            f"{item.sector_name}（{item.change_pct:+.2f}%，涨停 {item.limit_up_count} 家）"
            for item in sectors.leading
            if item.change_pct is not None
        ) or "无数据"

        user_prompt = PromptRenderer.render(
            prompt_config.user_prompt_template,
            trade_date=resolved_date.isoformat(),
            index_context=index_context,
            technical_context=technical_context,
            amount_text=_format_amount(stats.amount),
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
            section_instructions=_render_section_instructions(sections),
        )

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
            session, input_hash, model_name, contents, resolved_date, latency_ms
        )

        return _build_response(
            trade_date=resolved_date,
            contents=contents,
            sections=sections,
            model=model_name,
            generated_at=datetime.utcnow(),
            cached=False,
            edited=False,
        )
