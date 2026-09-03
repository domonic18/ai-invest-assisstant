"""AI 分析结果仓储：写入原始记录、读取 (skill_id, input_hash) 缓存。

供 chain_service / limit_up_ai_service / market_review_service 共享，
替代散落在 service 层的 ``text("INSERT INTO ai_analysis_result ...")`` raw SQL。
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_analysis_result import AiAnalysisResult


async def insert_result(
    session: AsyncSession,
    *,
    skill_id: str,
    input_hash: str | None,
    prompt_id: str | None,
    model: str | None,
    structured: dict[str, Any],
    latency_ms: int,
    status: str = "success",
    error_msg: str | None = None,
    stock_code: str | None = None,
) -> int:
    """写入一条 ai_analysis_result 记录并返回 id（不 commit）。

    raw_output 与 structured_output 同写入；structured_output 走 ORM JSONB
    列，避免手写 ``CAST(:x AS JSONB)``。个股级分析（如按股每日复盘）传入
    stock_code 以便按标的检索。
    """
    row = AiAnalysisResult(
        skill_id=skill_id,
        input_hash=input_hash,
        prompt_id=prompt_id,
        model=model,
        stock_code=stock_code,
        raw_output=str(structured),
        structured_output=structured,
        latency_ms=latency_ms,
        status=status,
        error_msg=error_msg,
    )
    session.add(row)
    await session.flush()
    return row.id


async def load_latest_success(
    session: AsyncSession, *, skill_id: str, input_hash: str
) -> AiAnalysisResult | None:
    """读取最近一条 success 状态的记录；无缓存返回 None。"""
    stmt = (
        select(AiAnalysisResult)
        .where(
            AiAnalysisResult.skill_id == skill_id,
            AiAnalysisResult.input_hash == input_hash,
            AiAnalysisResult.status == "success",
        )
        .order_by(AiAnalysisResult.created_at.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def load_success_by_hashes(
    session: AsyncSession, *, skill_id: str, input_hashes: list[str]
) -> list[AiAnalysisResult]:
    """按 input_hash 批量读取 success 记录，created_at 倒序（同 hash 去重由调用方做）。"""
    if not input_hashes:
        return []
    stmt = (
        select(AiAnalysisResult)
        .where(
            AiAnalysisResult.skill_id == skill_id,
            AiAnalysisResult.input_hash.in_(input_hashes),
            AiAnalysisResult.status == "success",
        )
        .order_by(AiAnalysisResult.created_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())
