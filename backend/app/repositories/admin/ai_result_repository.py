"""管理后台 AI 分析结果仓储：ai_analysis_result 按 (skill_id, input_hash) 通用聚合。

input_hash 是各 skill 统一的业务键指纹（同一业务键的全部生成历史共享同一 hash，
如 ``limit-up-review:<sha256>`` / ``<user_id>:<industry>:v<N>``），据此分组取最新行
即可覆盖全部 skill，无需任何 per-skill 的 JSONB 键表达式。
"""

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import ColumnElement, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.ai_analysis_result import AiAnalysisResult


def _created_at_range(
    start_date: date | None, end_date: date | None
) -> list[ColumnElement[bool]]:
    """把业务日期区间换算为 aware UTC 时间戳过滤（created_at 为 timestamptz）。"""
    conditions: list[ColumnElement[bool]] = []
    if start_date is not None:
        conditions.append(
            AiAnalysisResult.created_at
            >= datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        )
    if end_date is not None:
        conditions.append(
            AiAnalysisResult.created_at
            < datetime.combine(end_date, time.min, tzinfo=timezone.utc)
            + timedelta(days=1)
        )
    return conditions


def _base_filters(
    skill_id: str,
    status: str | None,
    start_date: date | None,
    end_date: date | None,
) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = [
        AiAnalysisResult.skill_id == skill_id,
    ]
    if status is not None:
        conditions.append(AiAnalysisResult.status == status)
    conditions.extend(_created_at_range(start_date, end_date))
    return conditions


async def list_paginated(
    session: AsyncSession,
    *,
    skill_id: str,
    page: int,
    page_size: int,
    status: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> tuple[list[AiAnalysisResult], int]:
    """分页返回每个业务键（input_hash）最新一条生成记录，附去重业务键总数。

    input_hash 本身无业务时序含义，故先在子查询内按 (hash, created_at desc)
    取每键最新行，外层再按 created_at desc 排序分页。
    """
    conditions = _base_filters(skill_id, status, start_date, end_date)

    latest_subq = (
        select(AiAnalysisResult)
        .distinct(AiAnalysisResult.input_hash)
        .where(*conditions)
        .order_by(AiAnalysisResult.input_hash, AiAnalysisResult.created_at.desc())
        .subquery()
    )
    latest = aliased(AiAnalysisResult, latest_subq)
    rows_stmt = (
        select(latest)
        .order_by(latest.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = list((await session.execute(rows_stmt)).scalars().all())

    hashes_subq = (
        select(AiAnalysisResult.input_hash)
        .where(*conditions)
        .distinct()
        .subquery()
    )
    total_stmt = select(func.count()).select_from(hashes_subq)
    total = (await session.execute(total_stmt)).scalar_one()
    return rows, total


async def counts_by_hash(
    session: AsyncSession, skill_id: str, input_hashes: list[str]
) -> dict[str, int]:
    """统计每个业务键的生成记录总数（含非 success 历史行）。"""
    if not input_hashes:
        return {}
    stmt = (
        select(AiAnalysisResult.input_hash, func.count())
        .where(
            AiAnalysisResult.skill_id == skill_id,
            AiAnalysisResult.input_hash.in_(input_hashes),
        )
        .group_by(AiAnalysisResult.input_hash)
    )
    rows = (await session.execute(stmt)).all()
    return {input_hash: count for input_hash, count in rows}


async def min_created_at(
    session: AsyncSession, skill_id: str
) -> datetime | None:
    """该 skill 最早一条记录的生成时间（reverse-hash 反查区间的下界）。"""
    stmt = select(func.min(AiAnalysisResult.created_at)).where(
        AiAnalysisResult.skill_id == skill_id
    )
    return (await session.execute(stmt)).scalar_one()


async def get_by_id(
    session: AsyncSession, row_id: int
) -> AiAnalysisResult | None:
    """按主键读取单条生成记录。"""
    return (
        await session.execute(
            select(AiAnalysisResult).where(AiAnalysisResult.id == row_id)
        )
    ).scalar_one_or_none()


async def delete_by_hash(
    session: AsyncSession, *, skill_id: str, input_hash: str
) -> int:
    """删除该业务键的全部生成记录（缓存清除语义），返回删除行数（不 commit）。"""
    stmt = delete(AiAnalysisResult).where(
        AiAnalysisResult.skill_id == skill_id,
        AiAnalysisResult.input_hash == input_hash,
    )
    result = await session.execute(stmt)
    return int(getattr(result, "rowcount", 0) or 0)


async def delete_by_id(session: AsyncSession, row_id: int) -> int:
    """按主键删除单条记录（无 input_hash 的历史数据兜底），不 commit。"""
    stmt = delete(AiAnalysisResult).where(AiAnalysisResult.id == row_id)
    result = await session.execute(stmt)
    return int(getattr(result, "rowcount", 0) or 0)
