"""AI 分析结果仓储：写入原始记录、读取 (skill_id, input_hash) 缓存。

供 chain_service / limit_up_ai_service / market_review_service 共享，
替代散落在 service 层的 ``text("INSERT INTO ai_analysis_result ...")`` raw SQL。
"""

from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.core.clock import utc_now
from app.models.ai_analysis_result import AiAnalysisResult

# 按标的枚举历史时只回看此窗口（日历标记场景约一个年视图），避免全历史
# JSONB 扫描随时间线性膨胀
_TRADE_DATES_WINDOW_DAYS = 400


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


async def list_success_trade_dates(
    session: AsyncSession, *, skill_id: str, stock_code: str | None = None
) -> list[date]:
    """聚合 success 记录中 structured_output.trade_date 的去重列表（升序）。

    供日历标记「哪些交易日已生成过分析」。stock_code 缺省时不过滤标的
    （市场级 skill 如大盘复盘）；trade_date 从 JSONB 解出，脏数据
    （缺失/非 ISO 格式）跳过而非中断。
    """
    conditions = [
        AiAnalysisResult.skill_id == skill_id,
        AiAnalysisResult.status == "success",
        AiAnalysisResult.created_at >= utc_now() - timedelta(days=_TRADE_DATES_WINDOW_DAYS),
    ]
    if stock_code is not None:
        conditions.append(AiAnalysisResult.stock_code == stock_code)
    stmt = select(AiAnalysisResult.structured_output).where(*conditions)
    rows = list((await session.execute(stmt)).scalars().all())
    dates: set[date] = set()
    for structured in rows:
        raw = (structured or {}).get("trade_date")
        try:
            dates.add(date.fromisoformat(str(raw)))
        except (TypeError, ValueError):
            continue
    return sorted(dates)


async def load_success_by_hashes(
    session: AsyncSession, *, skill_id: str, input_hashes: list[str]
) -> list[AiAnalysisResult]:
    """按 input_hash 批量读取最新的 success 记录（每 hash 一行，排除 raw_output）。"""
    if not input_hashes:
        return []
    stmt = (
        select(AiAnalysisResult)
        .where(
            AiAnalysisResult.skill_id == skill_id,
            AiAnalysisResult.input_hash.in_(input_hashes),
            AiAnalysisResult.status == "success",
        )
        .distinct(AiAnalysisResult.input_hash)
        .order_by(AiAnalysisResult.input_hash, AiAnalysisResult.created_at.desc())
        .options(
            load_only(
                AiAnalysisResult.input_hash,
                AiAnalysisResult.structured_output,
            )
        )
    )
    return list((await session.execute(stmt)).scalars().all())
