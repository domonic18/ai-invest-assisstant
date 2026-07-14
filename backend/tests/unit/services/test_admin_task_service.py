"""Unit tests for admin task service."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.collector_task import CollectorTaskCreate, CollectorTaskUpdate
from app.services.admin_task_service import AdminTaskService


def _result_mock(items=None, scalar=None):
    result = MagicMock()
    result.scalars.return_value.all.return_value = items or []
    result.scalar_one_or_none.return_value = scalar
    return result


@pytest.mark.unit
class TestAdminTaskService:
    @pytest.fixture
    def service(self) -> AdminTaskService:
        session = AsyncMock()
        session.add = MagicMock()
        return AdminTaskService(session)

    @pytest.mark.asyncio
    async def test_list_tasks(self, service: AdminTaskService) -> None:
        mock_task = MagicMock()
        service.session.execute.return_value = _result_mock([mock_task])
        service.session.scalar.return_value = 1

        items, total = await service.list_tasks()

        assert items == [mock_task]
        assert total == 1

    @pytest.mark.asyncio
    async def test_create_task(self, service: AdminTaskService) -> None:
        data = CollectorTaskCreate(
            task_name="kline",
            task_type="scheduled",
            source="tushare",
        )
        result = await service.create_task(data)

        assert result.task_name == "kline"
        service.session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_task(self, service: AdminTaskService) -> None:
        task = MagicMock()
        service.session.get.return_value = task

        result = await service.update_task(
            1, CollectorTaskUpdate(is_active=False)
        )

        assert result == task
        assert task.is_active is False

    @pytest.mark.asyncio
    async def test_pause_resume_trigger_task(self, service: AdminTaskService) -> None:
        task = MagicMock()
        task.is_active = True
        service.session.get.return_value = task

        paused = await service.pause_task(1)
        assert paused == task
        assert task.is_active is False

        resumed = await service.resume_task(1)
        assert resumed == task
        assert task.is_active is True

        triggered = await service.trigger_task(1)
        assert triggered == task
        assert task.last_status == "running"

    @pytest.mark.asyncio
    async def test_delete_task(self, service: AdminTaskService) -> None:
        task = MagicMock()
        service.session.get.return_value = task

        await service.delete_task(1)

        service.session.delete.assert_awaited_once_with(task)
