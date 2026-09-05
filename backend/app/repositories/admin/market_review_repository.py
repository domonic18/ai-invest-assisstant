"""管理后台大盘复盘仓储：按 trade_date（structured_output JSONB 内键）聚合查询。

trade_date 不是 ai_analysis_result 的物理列，统一通过
``structured_output["trade_date"].astext``（ISO 字符串，字典序即时序）查询。
"""

from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_analysis_result import AiAnalysisResult
from app.models.user_market_review import UserMarketReview

_trade_date_expr = AiAnalysisResult.structured_output["trade_date"].astext


def _base_filters(
    skill_id: str, start_date: date | None, end_date: date | None
) -> list:
    conditions = [
        AiAnalysisResult.skill_id == skill_id,
        AiAnalysisResult.status == "success",
    ]
    if start_date is not None:
        conditions.append(_trade_date_expr >= start_date.isoformat())
    if end_date is not None:
        conditions.append(_trade_date_expr <= end_date.isoformat())
    return conditions


async def list_paginated(
    session: AsyncSession,
    *,
    skill_id: str,
    page: int,
    page_size: int,
    start_date: date | None = None,
    end_date: date | None = None,
) -> tuple[list[AiAnalysisResult], int]:
    """分页返回每个交易日最新一条生成记录（DISTINCT ON），附去重日期总数。"""
    conditions = _base_filters(skill_id, start_date, end_date)

    rows_stmt = (
        select(AiAnalysisResult)
        .distinct(_trade_date_expr)
        .where(*conditions)
        .order_by(_trade_date_expr.desc(), AiAnalysisResult.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = list((await session.execute(rows_stmt)).scalars().all())

    dates_subq = (
        select(_trade_date_expr)
        .where(*conditions)
        .distinct()
        .subquery()
    )
    total_stmt = select(func.count()).select_from(dates_subq)
    total = (await session.execute(total_stmt)).scalar_one()
    return rows, total


async def counts_by_date(
    session: AsyncSession,
    skill_id: str,
    trade_dates: list[date],
) -> dict[date, int]:
    """统计每个交易日的生成记录总数（含非 success 历史行）。"""
    if not trade_dates:
        return {}
    conditions = [
        AiAnalysisResult.skill_id == skill_id,
        _trade_date_expr.in_([d.isoformat() for d in trade_dates]),
    ]
    stmt = (
        select(_trade_date_expr, func.count())
        .where(*conditions)
        .group_by(_trade_date_expr)
    )
    rows = (await session.execute(stmt)).all()
    return {date.fromisoformat(raw): count for raw, count in rows}


async def user_copy_counts(
    session: AsyncSession, trade_dates: list[date]
) -> dict[date, int]:
    """统计每个交易日的用户编辑副本数（user_market_review）。"""
    if not trade_dates:
        return {}
    stmt = (
        select(UserMarketReview.trade_date, func.count())
        .where(UserMarketReview.trade_date.in_(trade_dates))
        .group_by(UserMarketReview.trade_date)
    )
    rows = (await session.execute(stmt)).all()
    return {trade_date: count for trade_date, count in rows}


async def delete_by_date(
    session: AsyncSession, *, skill_id: str, trade_date: date
) -> int:
    """删除该交易日全部生成记录（含非 success），返回删除行数（不 commit）。"""
    stmt = delete(AiAnalysisResult).where(
        AiAnalysisResult.skill_id == skill_id,
        _trade_date_expr == trade_date.isoformat(),
    )
    result = await session.execute(stmt)
    return int(getattr(result, "rowcount", 0) or 0)
