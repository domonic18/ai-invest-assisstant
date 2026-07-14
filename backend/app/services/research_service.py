"""Research report business services."""

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news_announcement import NewsAnnouncement


async def list_reports(
    session: AsyncSession,
    stock_code: str | None = None,
    q: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[NewsAnnouncement], int]:
    """分页查询研报列表。

    Args:
        session: 数据库会话。
        stock_code: 按股票代码筛选。
        q: 按标题或内容关键词筛选。
        start_date: 发布日期起始。
        end_date: 发布日期截止。
        page: 页码。
        page_size: 每页数量。

    Returns:
        (研报列表, 总数)。
    """
    stmt = select(NewsAnnouncement).where(NewsAnnouncement.doc_type == "research")
    count_stmt = (
        select(func.count())
        .select_from(NewsAnnouncement)
        .where(NewsAnnouncement.doc_type == "research")
    )

    if stock_code:
        stmt = stmt.where(NewsAnnouncement.stock_code == stock_code)
        count_stmt = count_stmt.where(NewsAnnouncement.stock_code == stock_code)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            NewsAnnouncement.title.ilike(pattern)
            | NewsAnnouncement.content.ilike(pattern)
        )
        count_stmt = count_stmt.where(
            NewsAnnouncement.title.ilike(pattern)
            | NewsAnnouncement.content.ilike(pattern)
        )
    if start_date:
        stmt = stmt.where(NewsAnnouncement.publish_date >= start_date)
        count_stmt = count_stmt.where(NewsAnnouncement.publish_date >= start_date)
    if end_date:
        end_datetime = end_date + timedelta(days=1)
        stmt = stmt.where(NewsAnnouncement.publish_date < end_datetime)
        count_stmt = count_stmt.where(NewsAnnouncement.publish_date < end_datetime)

    stmt = (
        stmt.order_by(NewsAnnouncement.publish_date.desc().nullslast())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await session.execute(stmt)
    total = await session.scalar(count_stmt) or 0
    return list(result.scalars().all()), total


async def get_report(session: AsyncSession, report_id: int) -> NewsAnnouncement | None:
    """按 ID 查询研报详情。"""
    return await session.get(NewsAnnouncement, report_id)


async def summarize_report(session: AsyncSession, report_id: int) -> dict[str, Any]:
    """获取研报摘要。

    优先返回已有摘要；若不存在则返回正文前 500 字符；都没有则返回空字符串。

    Args:
        session: 数据库会话。
        report_id: 研报 ID。

    Returns:
        包含 summary 字段的字典。
    """
    report = await get_report(session, report_id)
    if report is None:
        raise ValueError(f"Research report {report_id} not found")

    if report.summary:
        return {"summary": report.summary}

    content = report.content or ""
    return {"summary": content[:500] if len(content) <= 500 else content[:500] + "..."}
