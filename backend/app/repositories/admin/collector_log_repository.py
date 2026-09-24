"""采集日志仓储。"""

from datetime import datetime, timedelta

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collector_log import CollectorLog
from app.repositories.base import BaseRepository


class CollectorLogRepository(BaseRepository[CollectorLog]):
    """采集执行日志的数据访问。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CollectorLog)

    async def list_recent(
        self,
        page: int,
        page_size: int,
        *,
        task_name: str | None = None,
        source: str | None = None,
        status: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
    ) -> tuple[int, list[CollectorLog]]:
        """分页返回采集日志（开始时间倒序，可按任务键/渠道/状态/时间区间过滤）。

        started_after 含下界、started_before 为排他上界，调用方负责换算为
        业务日期的 aware UTC 边界。
        """
        conditions = []
        if task_name:
            conditions.append(CollectorLog.task_name == task_name)
        if source:
            conditions.append(CollectorLog.source == source)
        if status:
            conditions.append(CollectorLog.status == status)
        if started_after:
            conditions.append(CollectorLog.started_at >= started_after)
        if started_before:
            conditions.append(CollectorLog.started_at < started_before)

        count_stmt = select(func.count()).select_from(CollectorLog)
        if conditions:
            count_stmt = count_stmt.where(*conditions)
        total: int = (await self.execute(count_stmt)).scalar_one()

        stmt = (
            select(CollectorLog)
            .order_by(desc(CollectorLog.started_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        if conditions:
            stmt = stmt.where(*conditions)
        result = await self.execute(stmt)
        return total, list(result.scalars().all())

    async def count_by_status_since(self, since: datetime) -> dict[str, int]:
        """按状态统计 since（含）之后的日志条数。"""
        stmt = (
            select(CollectorLog.status, func.count())
            .where(CollectorLog.started_at >= since)
            .group_by(CollectorLog.status)
        )
        result = await self.execute(stmt)
        return {status: count for status, count in result.all()}

    async def get_latest_running(self, *, max_age: timedelta) -> CollectorLog | None:
        """最近一条 running 日志；超过 max_age 视为僵行不返回。"""
        stmt = (
            select(CollectorLog)
            .where(CollectorLog.status == "running")
            .order_by(desc(CollectorLog.started_at))
            .limit(1)
        )
        row: CollectorLog | None = (await self.execute(stmt)).scalars().first()
        if row is None or row.started_at is None:
            return None
        if row.started_at < datetime.now(row.started_at.tzinfo) - max_age:
            return None
        return row

    async def list_recent_terminal(self, limit: int = 3) -> list[CollectorLog]:
        """最近 N 条已出终态（非 running）的日志，按开始时间倒序。"""
        stmt = (
            select(CollectorLog)
            .where(CollectorLog.status != "running")
            .order_by(desc(CollectorLog.started_at))
            .limit(limit)
        )
        result = await self.execute(stmt)
        return list(result.scalars().all())

    async def list_runs_for_task(
        self,
        task_name: str,
        *,
        since: datetime,
        source: str | None = None,
        limit: int = 500,
    ) -> list[CollectorLog]:
        """某任务自 since 起的运行日志，按开始时间倒序。

        task_name 语义为 TASK_SPECS 键（task_type），不是 collector_task 的
        实例名；渠道身份 = (task_type, source)，按渠道查询须传 source。
        """
        conditions = [
            CollectorLog.task_name == task_name,
            CollectorLog.started_at >= since,
        ]
        if source is not None:
            conditions.append(CollectorLog.source == source)
        stmt = (
            select(CollectorLog)
            .where(*conditions)
            .order_by(desc(CollectorLog.started_at))
            .limit(limit)
        )
        result = await self.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, log_id: int) -> CollectorLog | None:
        """按主键返回单条采集日志。"""
        return await self.session.get(CollectorLog, log_id)
