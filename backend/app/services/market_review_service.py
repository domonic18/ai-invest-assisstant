"""AI 大盘综述（LLM 复盘报告）服务。

生成结果按 (skill_id, input_hash=trade_date) 缓存在 ai_analysis_result 表，
支持强制重新生成。
"""

import hashlib
import time
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
from app.services import market_service
from app.services.llm_config_service import resolve_default_llm

SKILL_ID = "market-daily-review"


class MarketReviewContent(BaseModel):
    """LLM 结构化输出。"""

    overview: str
    emotion_analysis: str
    capital_analysis: str
    risk_advice: str


def _input_hash(trade_date: date) -> str:
    return hashlib.sha256(f"{SKILL_ID}:{trade_date.isoformat()}".encode()).hexdigest()


def _format_amount(amount: float | None) -> str:
    if amount is None:
        return "未知"
    if amount >= 1e12:
        return f"{amount / 1e12:.2f} 万亿元"
    return f"{amount / 1e8:.0f} 亿元"


async def _load_cached(
    session: AsyncSession, input_hash: str
) -> MarketReviewResponse | None:
    row = (
        await session.execute(
            text(
                """
                SELECT structured_output, model, created_at
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
    return MarketReviewResponse(
        trade_date=date.fromisoformat(output["trade_date"]),
        overview=output["overview"],
        emotion_analysis=output["emotion_analysis"],
        capital_analysis=output["capital_analysis"],
        risk_advice=output["risk_advice"],
        model=row["model"],
        generated_at=row["created_at"],
        cached=True,
    )


async def _persist(
    session: AsyncSession,
    input_hash: str,
    model: str,
    content: MarketReviewContent,
    trade_date: date,
    latency_ms: int,
) -> None:
    import json

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
) -> MarketReviewResponse:
    """生成（或读取缓存的）AI 大盘综述。"""
    stats = await market_service.get_market_stats(session, trade_date)
    resolved_date = stats.trade_date
    input_hash = _input_hash(resolved_date)

    if not regenerate:
        cached = await _load_cached(session, input_hash)
        if cached:
            return cached

    indices = await market_service.get_index_quotes(resolved_date)
    limit_up = await market_service.get_limit_up(session, resolved_date)
    sectors = await market_service.get_sector_overview(session, resolved_date)

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
            f"{stats.broken_rate * 100:.1f}%" if stats.broken_rate is not None else "未知"
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
    )
