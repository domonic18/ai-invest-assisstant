"""采集日志业务服务。"""

from datetime import date, datetime, time, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.exceptions import BadRequestError
from app.models.collector_dead_letter import CollectorDeadLetter
from app.models.collector_log import CollectorLog
from app.repositories.admin.collector_dead_letter_repository import (
    CollectorDeadLetterRepository,
)
from app.repositories.admin.collector_log_repository import CollectorLogRepository
from app.schemas.collector import CollectorLogSummaryResponse

# collector_log.status 全量枚举（collector/core/base.py CollectStatus + runner 写入），
# 仅日志查询服务消费，作为列表筛选参数的白名单。
LOG_STATUSES = ("pending", "running", "success", "partial", "failed", "skipped")


class CollectorLogService:
    """采集执行日志与死信查询服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = CollectorLogRepository(session)
        self.dead_letter_repo = CollectorDeadLetterRepository(session)

    async def list_recent(
        self,
        page: int,
        page_size: int,
        *,
        task_name: str | None = None,
        source: str | None = None,
        status: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> tuple[int, list[CollectorLog]]:
        """分页查询采集执行日志，按开始时间倒序（可按任务键/渠道/状态/日期区间过滤）。

        start_date/end_date 为 Asia/Shanghai 业务日历日，换算为 aware UTC
        的 [当日 00:00, 次日 00:00) 区间。
        """
        if status is not None and status not in LOG_STATUSES:
            raise BadRequestError(
                f"status must be one of {', '.join(LOG_STATUSES)}"
            )
        if start_date and end_date and start_date > end_date:
            raise BadRequestError("start_date must not be after end_date")
        started_after = (
            datetime.combine(start_date, time.min, tzinfo=clock.CN_TZ)
            if start_date
            else None
        )
        started_before = (
            datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=clock.CN_TZ)
            if end_date
            else None
        )
        return await self.repo.list_recent(
            page,
            page_size,
            task_name=task_name,
            source=source,
            status=status,
            started_after=started_after,
            started_before=started_before,
        )

    async def get_today_summary(self) -> CollectorLogSummaryResponse:
        """今日（Asia/Shanghai 日历日）采集日志按状态计数。"""
        today = clock.today_cn()
        since = datetime.combine(today, time.min, tzinfo=clock.CN_TZ)
        counts = await self.repo.count_by_status_since(since)
        return CollectorLogSummaryResponse(
            date=today.isoformat(),
            success_count=counts.get("success", 0),
            partial_count=counts.get("partial", 0),
            failed_count=counts.get("failed", 0),
            skipped_count=counts.get("skipped", 0),
            running_count=counts.get("running", 0),
            pending_count=counts.get("pending", 0),
        )

    async def get_by_id(self, log_id: int) -> CollectorLog | None:
        """按主键查询单条采集执行日志。"""
        return await self.repo.get_by_id(log_id)

    async def list_dead_letters(
        self, page: int = 1, page_size: int = 20
    ) -> tuple[int, list[CollectorDeadLetter]]:
        """分页查询采集死信，按创建时间倒序。"""
        offset = (page - 1) * page_size
        return await self.dead_letter_repo.list_paginated(offset, page_size)
