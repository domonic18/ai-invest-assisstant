"""Tests for the generic Celery collector task wrapper."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from celery.exceptions import SoftTimeLimitExceeded

from collector.celery_tasks import (
    AsyncTask,
    _result_to_dict,
    run_collector_task,
)
from collector.core.base import CollectResult, CollectStatus


@pytest.mark.unit
class TestResultToDict:
    def test_serializes_result(self) -> None:
        result = CollectResult(
            source="sina",
            data_type="quote",
            status=CollectStatus.SUCCESS,
            items_collected=10,
            items_stored=10,
            errors=[],
        )
        data = _result_to_dict(result)
        assert data["source"] == "sina"
        assert data["status"] == "success"
        assert data["items_stored"] == 10


@pytest.mark.unit
class TestAsyncTask:
    def test_ensure_loop_creates_loop_on_first_call(self) -> None:
        task = AsyncTask()
        loop = task._ensure_loop()
        assert loop is not None
        assert not loop.is_closed()
        assert asyncio.get_event_loop() is loop
        loop.close()

    def test_ensure_loop_reuses_existing_loop(self) -> None:
        task = AsyncTask()
        first = task._ensure_loop()
        second = task._ensure_loop()
        assert first is second
        first.close()

    def test_ensure_loop_recreates_closed_loop(self) -> None:
        task = AsyncTask()
        old_loop = task._ensure_loop()
        old_loop.close()
        new_loop = task._ensure_loop()
        assert new_loop is not old_loop
        assert not new_loop.is_closed()
        new_loop.close()


@pytest.mark.unit
class TestLogAwareTask:
    def test_on_failure_writes_dead_letter(self) -> None:
        task = run_collector_task
        task.push_request(id="task-id", retries=2)

        payload = {"task": "quote", "log_id": 42, "preferred_source": "sina"}
        exc = ValueError("boom")

        with patch("collector.celery_tasks._mark_log_failed", new=AsyncMock()) as mock_mark:
            with patch("collector.celery_tasks._write_dead_letter", new=AsyncMock()) as mock_dl:
                task.on_failure(
                    exc,
                    "task-id",
                    (payload,),
                    {},
                    None,
                )

        task.pop_request()

        mock_mark.assert_awaited_once_with(42, exc)
        mock_dl.assert_awaited_once()
        call_kwargs = mock_dl.await_args.kwargs
        assert call_kwargs["task_name"] == "quote"
        assert call_kwargs["celery_task_id"] == "task-id"
        assert call_kwargs["retry_count"] == 2
        assert "boom" in call_kwargs["error_msg"]

    def test_on_failure_uses_persistent_loop(self) -> None:
        task = run_collector_task
        task.push_request(id="task-id", retries=0)
        loop = task._ensure_loop()

        payload = {"task": "quote", "log_id": 42}
        exc = ValueError("boom")

        with patch("collector.celery_tasks._mark_log_failed", new=AsyncMock()) as mock_mark:
            with patch("collector.celery_tasks._write_dead_letter", new=AsyncMock()) as mock_dl:
                task.on_failure(exc, "task-id", (payload,), {}, None)

        task.pop_request()
        loop.close()

        mock_mark.assert_awaited_once()
        mock_dl.assert_awaited_once()


@pytest.mark.unit
class TestRunCollectorTask:
    @patch("collector.celery_tasks.run_task", new_callable=AsyncMock)
    def test_success_updates_schedule_state(self, mock_run_task: AsyncMock) -> None:
        result = CollectResult(
            source="sina",
            data_type="quote",
            status=CollectStatus.SUCCESS,
            items_collected=5,
            items_stored=5,
            errors=[],
        )
        mock_run_task.return_value = result

        task = run_collector_task
        task.push_request(id="celery-id")

        with patch("collector.celery_tasks._update_task_schedule_state", new=AsyncMock()) as mock_update:
            payload = {"task": "quote"}
            returned = task.run(payload)

        task.pop_request()

        assert returned["status"] == "success"
        mock_update.assert_awaited_once()

    @patch("collector.celery_tasks.run_task", new_callable=AsyncMock)
    def test_soft_timeout_marks_log_failed(self, mock_run_task: AsyncMock) -> None:
        mock_run_task.side_effect = SoftTimeLimitExceeded()

        task = run_collector_task
        task.push_request(id="celery-id", retries=0)

        with patch("collector.celery_tasks._mark_log_timeout", new=AsyncMock()) as mock_timeout:
            with patch("collector.celery_tasks._update_task_schedule_state", new=AsyncMock()):
                with pytest.raises(SoftTimeLimitExceeded):
                    task.run({"task": "quote", "log_id": 7})

        task.pop_request()

        mock_timeout.assert_awaited_once_with(7)

    @patch("collector.celery_tasks.run_task", new_callable=AsyncMock)
    def test_consecutive_runs_reuse_same_loop(self, mock_run_task: AsyncMock) -> None:
        """Two task runs in the same child process should share one event loop."""
        mock_run_task.return_value = CollectResult(
            source="sina",
            data_type="quote",
            status=CollectStatus.SUCCESS,
            items_collected=1,
            items_stored=1,
            errors=[],
        )

        task = run_collector_task
        task.push_request(id="first-id")

        with patch("collector.celery_tasks._update_task_schedule_state", new=AsyncMock()):
            task.run({"task": "quote"})
            first_loop = task._loop
            task.run({"task": "quote"})
            second_loop = task._loop

        task.pop_request()

        assert first_loop is second_loop
        assert first_loop is not None
        assert not first_loop.is_closed()
        first_loop.close()

    @patch("collector.celery_tasks.run_task", new_callable=AsyncMock)
    def test_consecutive_runs_do_not_dispose_engines(self, mock_run_task: AsyncMock) -> None:
        """With a persistent loop, engines should not be disposed between tasks."""
        mock_run_task.return_value = CollectResult(
            source="sina",
            data_type="quote",
            status=CollectStatus.SUCCESS,
            items_collected=1,
            items_stored=1,
            errors=[],
        )

        task = run_collector_task
        task.push_request(id="first-id")

        with patch("collector.celery_tasks._update_task_schedule_state", new=AsyncMock()):
            with patch("collector.celery_tasks._dispose_async_engines") as mock_dispose:
                task.run({"task": "quote"})
                task.run({"task": "quote"})

        task.pop_request()

        mock_dispose.assert_not_called()
        if task._loop is not None:
            task._loop.close()
