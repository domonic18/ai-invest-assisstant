"""collector 任务派发器契约测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from collector.runtime.dispatcher import dispatch_collector_task


@pytest.mark.unit
class TestDispatchCollectorTask:
    @pytest.mark.asyncio
    async def test_dispatches_via_celery_by_default(self) -> None:
        session = AsyncMock()
        session.scalar.return_value = None
        session.flush = AsyncMock()
        session.refresh = AsyncMock(return_value=None)
        session.commit = AsyncMock()

        mock_result = MagicMock()
        mock_result.id = "celery-task-uuid"
        mock_task = MagicMock()
        mock_task.apply_async.return_value = mock_result

        with patch("collector.celery_tasks.run_collector_task", mock_task):
            log = await dispatch_collector_task(
                session=session,
                task_name="quote",
                params={"preferred_source": "sina"},
            )

        assert log.celery_task_id == "celery-task-uuid"
        mock_task.apply_async.assert_called_once()
        call_kwargs = mock_task.apply_async.call_args.kwargs
        assert call_kwargs["queue"] == "collector.realtime"
        assert "soft_time_limit" in call_kwargs
        assert "max_retries" in call_kwargs
        session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_respects_collector_task_queue_override(self) -> None:
        session = AsyncMock()
        session.scalar.return_value = "collector.heavy"
        session.commit = AsyncMock()
        mock_log = MagicMock()
        mock_log.id = 124

        mock_result = MagicMock()
        mock_result.id = "celery-task-uuid-2"
        mock_task = MagicMock()
        mock_task.apply_async.return_value = mock_result

        with patch("collector.celery_tasks.run_collector_task", mock_task):
            log = await dispatch_collector_task(
                session=session,
                task_name="quote",
                params={"preferred_source": "sina"},
            )

        assert log.celery_task_id == "celery-task-uuid-2"
        call_kwargs = mock_task.apply_async.call_args.kwargs
        assert call_kwargs["queue"] == "collector.heavy"
