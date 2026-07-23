"""AI 大盘综述（LLM 复盘报告）服务。

生成结果按 (skill_id, input_hash=trade_date) 缓存在 ai_analysis_result 表作为
共享 base；用户编辑副本保存在 user_market_review 表，读取时优先 overlay。
生成逻辑统一加 Redis 分布式锁，避免多租户场景下重复调用 LLM。
"""

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, cast

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.core.llm_router import build_agent
from app.agent.core.prompt_loader import PromptLoader
from app.agent.core.prompt_renderer import PromptRenderer
from app.core.config import get_settings
from app.schemas.market import MarketReviewResponse
from app.services import index_technical_service, market_service
from app.services.llm_config_service import resolve_default_llm
from collector.core.locks import redis_lock

SKILL_ID = "market-daily-review"


class ReviewNotFoundError(Exception):
    """指定交易日不存在已生成的 AI 复盘。"""


class NonTradingDayError(Exception):
    """指定日期不是交易日，每日复盘只对交易日有效。"""


class ReviewGenerationLockedError(Exception):
    """其他实例正在生成同交易日的大盘综述。"""


class MarketReviewContent(BaseModel):
    """LLM 结构化输出。"""

    overview: str
    emotion_analysis: str
    capital_analysis: str
    risk_advice: str


@dataclass
class _BaseReview:
    """共享 base 记录（含数据库主键，用于用户编辑副本关联）。"""

    id: int
    response: MarketReviewResponse


def _input_hash(trade_date: date) -> str:
    return hashlib.sha256(f"{SKILL_ID}:{trade_date.isoformat()}".encode()).hexdigest()


def _format_amount(amount: float | None) -> str:
    if amount is None:
        return "未知"
    if amount >= 1e12:
        return f"{amount / 1e12:.2f} 万亿元"
    return f"{amount / 1e8:.0f} 亿元"


async def _load_base_review(
    session: AsyncSession, trade_date: date
) -> _BaseReview | None:
    """读取共享 base 记录。"""
    input_hash = _input_hash(trade_date)
    row = (
        await session.execute(
            text(
                """
                SELECT id, structured_output, model, created_at
                FROM ai_analysis_result
                WHERE skill_id = :skill_id AND input_hash = :input_hash
                  AND status = 'success'
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"skill_id": SKILL_ID, "input_hash": input_hash},
        )
    ).mappings().first()
    if not row or not row["structured_output"]:
        return None
    output = row["structured_output"]
    return _BaseReview(
        id=row["id"],
        response=MarketReviewResponse(
            trade_date=date.fromisoformat(output["trade_date"]),
            overview=output["overview"],
            emotion_analysis=output["emotion_analysis"],
            capital_analysis=output["capital_analysis"],
            risk_advice=output["risk_advice"],
            model=row["model"],
            generated_at=row["created_at"],
            cached=True,
            edited=False,
        ),
    )


async def _load_user_edit(
    session: AsyncSession, user_id: int, trade_date: date
) -> MarketReviewResponse | None:
    """读取用户编辑副本。"""
    row = (
        await session.execute(
            text(
                """
                SELECT overview, emotion_analysis, capital_analysis, risk_advice,
                       model, generated_at, created_at
                FROM user_market_review
                WHERE user_id = :user_id AND trade_date = :trade_date
                LIMIT 1
                """
            ),
            {"user_id": user_id, "trade_date": trade_date},
        )
    ).mappings().first()
    if not row:
        return None
    return MarketReviewResponse(
        trade_date=trade_date,
        overview=row["overview"],
        emotion_analysis=row["emotion_analysis"],
        capital_analysis=row["capital_analysis"],
        risk_advice=row["risk_advice"],
        model=row["model"],
        generated_at=row["generated_at"] or row["created_at"],
        cached=True,
        edited=True,
    )


async def _resolve_trade_date(
    session: AsyncSession, trade_date: date | None
) -> date:
    stats = await market_service.get_market_stats(session, trade_date)
    return stats.trade_date


async def _assert_trading_day(session: AsyncSession, day: date) -> None:
    if not await market_service.is_trading_day(session, day):
        raise NonTradingDayError(f"{day.isoformat()} 不是交易日，每日复盘只对交易日有效")


async def get_market_review(
    session: AsyncSession,
    user_id: int,
    trade_date: date | None = None,
) -> MarketReviewResponse | None:
    """读取用户视图的大盘综述：优先返回用户编辑版，否则回退共享 base。

    只读，不触发 LLM 生成。
    """
    if trade_date is not None:
        await _assert_trading_day(session, trade_date)
    resolved_date = await _resolve_trade_date(session, trade_date)

    user_review = await _load_user_edit(session, user_id, resolved_date)
    if user_review is not None:
        return user_review

    base = await _load_base_review(session, resolved_date)
    return base.response if base is not None else None


async def update_market_review(
    session: AsyncSession,
    user_id: int,
    trade_date: date,
    content: MarketReviewContent,
) -> MarketReviewResponse:
    """保存用户编辑的复盘内容到个人账户（不影响共享 base）。"""
    await _assert_trading_day(session, trade_date)

    base = await _load_base_review(session, trade_date)
    if base is None:
        raise ReviewNotFoundError(f"{trade_date.isoformat()} 尚未生成 AI 复盘")

    await session.execute(
        text(
            """
            INSERT INTO user_market_review
                (user_id, trade_date, overview, emotion_analysis,
                 capital_analysis, risk_advice, model, generated_at, base_review_id)
            VALUES
                (:user_id, :trade_date, :overview, :emotion_analysis,
                 :capital_analysis, :risk_advice, :model, :generated_at, :base_review_id)
            ON CONFLICT (user_id, trade_date) DO UPDATE
            SET overview = EXCLUDED.overview,
                emotion_analysis = EXCLUDED.emotion_analysis,
                capital_analysis = EXCLUDED.capital_analysis,
                risk_advice = EXCLUDED.risk_advice,
                model = EXCLUDED.model,
                generated_at = EXCLUDED.generated_at,
                base_review_id = EXCLUDED.base_review_id,
                updated_at = NOW()
            """
        ),
        {
            "user_id": user_id,
            "trade_date": trade_date,
            "overview": content.overview,
            "emotion_analysis": content.emotion_analysis,
            "capital_analysis": content.capital_analysis,
            "risk_advice": content.risk_advice,
            "model": base.response.model,
            "generated_at": base.response.generated_at,
            "base_review_id": base.id,
        },
    )
    await session.commit()

    return MarketReviewResponse(
        trade_date=trade_date,
        overview=content.overview,
        emotion_analysis=content.emotion_analysis,
        capital_analysis=content.capital_analysis,
        risk_advice=content.risk_advice,
        model=base.response.model,
        generated_at=base.response.generated_at,
        cached=True,
        edited=True,
    )


async def _persist(
    session: AsyncSession,
    input_hash: str,
    model: str,
    content: MarketReviewContent,
    trade_date: date,
    latency_ms: int,
) -> None:
    structured: dict[str, Any] = {
        "trade_date": trade_date.isoformat(),
        **content.model_dump(),
    }
    await session.execute(
        text(
            """
            INSERT INTO ai_analysis_result
                (skill_id, input_hash, prompt_id, model, raw_output,
                 structured_output, latency_ms, status)
            VALUES
                (:skill_id, :input_hash, :prompt_id, :model, :raw_output,
                 CAST(:structured_output AS JSONB), :latency_ms, 'success')
            """
        ),
        {
            "skill_id": SKILL_ID,
            "input_hash": input_hash,
            "prompt_id": SKILL_ID,
            "model": model,
            "raw_output": json.dumps(structured, ensure_ascii=False),
            "structured_output": json.dumps(structured, ensure_ascii=False),
            "latency_ms": latency_ms,
        },
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
    if trade_date is not None:
        await _assert_trading_day(session, trade_date)
    stats = await market_service.get_market_stats(session, trade_date)
    resolved_date = stats.trade_date
    input_hash = _input_hash(resolved_date)

    if not regenerate:
        cached = await _load_base_review(session, resolved_date)
        if cached is not None:
            return cached.response

    async with redis_lock(
        f"market-daily-review:{resolved_date}",
        ttl=300,
        blocking=blocking,
        blocking_timeout=blocking_timeout,
    ) as acquired:
        if not acquired:
            cached = await _load_base_review(session, resolved_date)
            if cached is not None:
                return cached.response
            raise ReviewGenerationLockedError(
                f"其他实例正在生成 {resolved_date.isoformat()} 的大盘综述"
            )

        if not regenerate:
            cached = await _load_base_review(session, resolved_date)
            if cached is not None:
                return cached.response

        indices = await market_service.get_index_quotes(session, resolved_date)
        limit_up = await market_service.get_limit_up(session, resolved_date)
        sectors = await market_service.get_sector_overview(session, resolved_date)
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

        prompt_loader = PromptLoader(get_settings().prompts_dir)
        prompt_config = prompt_loader.load("skills", SKILL_ID)
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
        )

        resolved = await resolve_default_llm(session)
        model_config = {
            "provider": resolved.provider,
            "model": resolved.model_name,
            "api_key": resolved.api_key,
            "base_url": resolved.base_url,
        }
        agent = build_agent(
            prompt_config=prompt_config,
            model_config=model_config,
            result_type=MarketReviewContent,
        )

        started = time.perf_counter()
        result = await agent.run(user_prompt)
        latency_ms = int((time.perf_counter() - started) * 1000)
        content = cast(MarketReviewContent, result.output)

        model_name = f"{resolved.provider}/{resolved.model_name}"
        await _persist(session, input_hash, model_name, content, resolved_date, latency_ms)

        return MarketReviewResponse(
            trade_date=resolved_date,
            overview=content.overview,
            emotion_analysis=content.emotion_analysis,
            capital_analysis=content.capital_analysis,
            risk_advice=content.risk_advice,
            model=model_name,
            generated_at=datetime.utcnow(),
            cached=False,
            edited=False,
        )
