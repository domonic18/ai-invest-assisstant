"""Admin collector task business services."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collector_task import CollectorTask
from app.schemas.collector_task import CollectorTaskCreate, CollectorTaskUpdate


class AdminTaskService:
    """后台采集任务管理服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_tasks(
        self, page: int = 1, page_size: int = 20
    ) -> tuple[list[CollectorTask], int]:
        """分页查询采集任务列表。"""
        stmt = (
            select(CollectorTask)
            .order_by(CollectorTask.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        count_stmt = select(func.count()).select_from(CollectorTask)
        result = await self.session.execute(stmt)
        total = await self.session.scalar(count_stmt) or 0
        return list(result.scalars().all()), total

    async def create_task(self, data: CollectorTaskCreate) -> CollectorTask:
        """创建采集任务。"""
        task = CollectorTask(
            task_name=data.task_name,
            task_type=data.task_type,
            source=data.source,
            schedule=data.schedule,
            is_active=data.is_active,
        )
        self.session.add(task)
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def update_task(
        self, task_id: int, data: CollectorTaskUpdate
    ) -> CollectorTask | None:
        """更新采集任务。"""
        task = await self.session.get(CollectorTask, task_id)
        if not task:
            return None

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(task, field, value)

        task.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def delete_task(self, task_id: int) -> None:
        """删除采集任务。"""
        task = await self.session.get(CollectorTask, task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        await self.session.delete(task)
        await self.session.flush()

    async def pause_task(self, task_id: int) -> CollectorTask | None:
        """暂停采集任务。"""
        task = await self.session.get(CollectorTask, task_id)
        if not task:
            return None
        task.is_active = False
        task.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def resume_task(self, task_id: int) -> CollectorTask | None:
        """恢复采集任务。"""
        task = await self.session.get(CollectorTask, task_id)
        if not task:
            return None
        task.is_active = True
        task.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def trigger_task(self, task_id: int) -> CollectorTask | None:
        """触发采集任务，更新最后运行时间。"""
        task = await self.session.get(CollectorTask, task_id)
        if not task:
            return None
        task.last_run_at = datetime.now(timezone.utc)
        task.last_status = "running"
        task.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(task)
        return task

    def _to_response(self, task: CollectorTask) -> dict[str, Any]:
        """序列化为采集任务响应字典。"""
        return {
            "id": task.id,
            "task_name": task.task_name,
            "task_type": task.task_type,
            "source": task.source,
            "schedule": task.schedule,
            "is_active": task.is_active,
            "last_run_at": task.last_run_at,
            "last_status": task.last_status,
            "last_error": task.last_error,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }
