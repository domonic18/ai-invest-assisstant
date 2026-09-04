"""采集日志仓储。"""

from datetime import datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collector_log import CollectorLog
from app.repositories.base import BaseRepository


class CollectorLogRepository(BaseRepository[CollectorLog]):
    """采集执行日志的数据访问。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CollectorLog)

    async def list_recent(self, limit: int = 50) -> list[CollectorLog]:
        """按开始时间倒序返回最近的采集日志。"""
        stmt = select(CollectorLog).order_by(desc(CollectorLog.started_at)).limit(limit)
        result = await self.execute(stmt)
        return list(result.scalars().all())

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
        self, task_name: str, *, since: datetime, limit: int = 500
    ) -> list[CollectorLog]:
        """某任务自 since 起的运行日志，按开始时间倒序。"""
        stmt = (
            select(CollectorLog)
            .where(
                CollectorLog.task_name == task_name,
                CollectorLog.started_at >= since,
            )
            .order_by(desc(CollectorLog.started_at))
            .limit(limit)
        )
        result = await self.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, log_id: int) -> CollectorLog | None:
        """按主键返回单条采集日志。"""
        return await self.session.get(CollectorLog, log_id)
