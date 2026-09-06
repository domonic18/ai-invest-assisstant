"""后台采集任务业务服务。"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.collector_task import CollectorTask
from app.repositories.admin.collector_task_repository import CollectorTaskRepository
from app.schemas.collector_task import CollectorTaskCreate, CollectorTaskUpdate


class AdminTaskService:
    """后台采集任务管理服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = CollectorTaskRepository(session)

    async def list_tasks(
        self, page: int = 1, page_size: int = 20
    ) -> tuple[list[CollectorTask], int]:
        """分页查询采集任务列表。"""
        offset = (page - 1) * page_size
        return await self.repo.list_paginated(offset=offset, limit=page_size)

    async def get_task(self, task_id: int) -> CollectorTask:
        """按 ID 查询采集任务，缺失时抛 NotFoundError。"""
        task = await self.repo.get(task_id)
        if not task:
            raise NotFoundError(f"Task {task_id} not found")
        return task

    async def create_task(self, data: CollectorTaskCreate) -> CollectorTask:
        """创建采集任务。"""
        task = CollectorTask(
            task_name=data.task_name,
            task_type=data.task_type,
            source=data.source,
            schedule=data.schedule,
            queue=data.queue,
            is_active=data.is_active,
        )
        self.repo.add(task)
        await self.session.commit()
        await self.repo.refresh(task)
        return task

    async def update_task(self, task_id: int, data: CollectorTaskUpdate) -> CollectorTask:
        """更新采集任务，缺失时抛 NotFoundError。"""
        task = await self.get_task(task_id)

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(task, field, value)

        task.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.repo.refresh(task)
        return task

    async def delete_task(self, task_id: int) -> None:
        """删除采集任务。"""
        task = await self.get_task(task_id)
        await self.repo.delete(task)
        await self.session.commit()

    async def pause_task(self, task_id: int) -> CollectorTask:
        """暂停采集任务。"""
        return await self._set_active(task_id, False)

    async def resume_task(self, task_id: int) -> CollectorTask:
        """恢复采集任务。"""
        return await self._set_active(task_id, True)

    async def trigger_task(self, task_id: int) -> CollectorTask:
        """触发采集任务：置 running 并派发到采集器队列。

        dispatcher 内部会 commit，必须在状态提交之后调用；延迟导入
        collector.runtime 避免环导入。
        """
        task = await self.get_task(task_id)
        task.last_run_at = datetime.now(timezone.utc)
        task.last_status = "running"
        task.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.repo.refresh(task)

        from collector.runtime.dispatcher import dispatch_collector_task

        await dispatch_collector_task(
            session=self.session,
            task_name=task.task_type,
            params={"preferred_source": task.source},
        )
        return task

    async def _set_active(self, task_id: int, active: bool) -> CollectorTask:
        """启用或停用任务。"""
        task = await self.get_task(task_id)
        task.is_active = active
        task.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.repo.refresh(task)
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
