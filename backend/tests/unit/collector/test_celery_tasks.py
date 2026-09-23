"""通用 Celery 采集任务包装器契约测试。"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from celery.exceptions import Retry, SoftTimeLimitExceeded

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
    def test_soft_timeout_below_max_retries_schedules_retry(self, mock_run_task: AsyncMock) -> None:
        """软超时先按队列退避策略重试，不写终态日志。"""
        mock_run_task.side_effect = SoftTimeLimitExceeded()

        task = run_collector_task
        task.push_request(id="celery-id", retries=0)

        retry_kwargs: dict = {}

        def _fake_retry(**kwargs: object) -> None:
            retry_kwargs.update(kwargs)
            raise Retry()

        with (
            patch.object(run_collector_task, "retry", side_effect=_fake_retry),
            patch("collector.celery_tasks._mark_log_timeout", new=AsyncMock()) as mock_timeout,
            patch(
                "collector.celery_tasks._update_task_schedule_state", new=AsyncMock()
            ) as mock_update,
        ):
            with pytest.raises(Retry):
                task.run({"task": "quote", "log_id": 7})

        task.pop_request()

        # quote → realtime 队列：backoff 30s / 最多 3 次。
        assert retry_kwargs["countdown"] == 30
        assert retry_kwargs["max_retries"] == 3
        assert isinstance(retry_kwargs["exc"], SoftTimeLimitExceeded)
        mock_timeout.assert_not_awaited()
        mock_update.assert_awaited_once()

    @patch("collector.celery_tasks.run_task", new_callable=AsyncMock)
    def test_soft_timeout_exhausted_marks_log_failed(self, mock_run_task: AsyncMock) -> None:
        """重试耗尽后软超时走终态：标记日志失败并向上抛出（进入死信）。"""
        mock_run_task.side_effect = SoftTimeLimitExceeded()

        task = run_collector_task
        task.push_request(id="celery-id", retries=3)

        with patch("collector.celery_tasks._mark_log_timeout", new=AsyncMock()) as mock_timeout:
            with patch(
                "collector.celery_tasks._update_task_schedule_state", new=AsyncMock()
            ) as mock_update:
                with pytest.raises(SoftTimeLimitExceeded):
                    task.run({"task": "quote", "log_id": 7})

        task.pop_request()

        mock_timeout.assert_awaited_once_with(7)
        mock_update.assert_awaited_once()

    def test_soft_timeout_from_loop_frame_still_retries(self) -> None:
        """软限信号打断事件循环帧（select 空闲期）时异常从 run_until_complete
        冒出——重试处理挂在外层必须仍然生效（2026-09-23 本地栈实测发现的
        丢失路径：旧实现挂在协程内，该抛点直接终态失败）。"""
        from collections.abc import Coroutine
        from unittest.mock import MagicMock

        task = run_collector_task
        task.push_request(id="celery-id", retries=0)

        mock_loop = MagicMock()
        ruc_calls = {"n": 0}

        def _fake_run_until_complete(coro: object) -> object:
            ruc_calls["n"] += 1
            if isinstance(coro, Coroutine):
                coro.close()  # 防 RuntimeWarning: coroutine never awaited
            if ruc_calls["n"] == 1:  # 第一次 = _execute，被软限信号打断
                raise SoftTimeLimitExceeded()
            return None

        mock_loop.run_until_complete.side_effect = _fake_run_until_complete

        retry_kwargs: dict = {}

        def _fake_retry(**kwargs: object) -> None:
            retry_kwargs.update(kwargs)
            raise Retry()

        with (
            patch.object(run_collector_task, "_ensure_loop", return_value=mock_loop),
            patch.object(run_collector_task, "retry", side_effect=_fake_retry),
            patch(
                "collector.celery_tasks._update_task_schedule_state", new=AsyncMock()
            ) as mock_update,
            patch(
                "collector.celery_tasks._mark_log_timeout", new=AsyncMock()
            ) as mock_timeout,
        ):
            with pytest.raises(Retry):
                task.run({"task": "quote", "log_id": 7})

        task.pop_request()

        assert retry_kwargs["countdown"] == 30
        assert retry_kwargs["max_retries"] == 3
        assert ruc_calls["n"] == 3  # _execute(软限) → 清理僵尸协程 → 状态回写
        # mock loop 不真正跑协程，只断言调度了状态回写
        mock_update.assert_called_once()
        mock_timeout.assert_not_called()

    @patch("collector.celery_tasks.run_task", new_callable=AsyncMock)
    def test_not_ready_error_schedules_retry(self, mock_run_task: AsyncMock) -> None:
        """输入数据未就绪时按 10 分钟退避重试，而非当天直接失败。"""
        from app.services.review import ReviewInputDataNotReadyError

        mock_run_task.side_effect = ReviewInputDataNotReadyError()

        task = run_collector_task
        task.push_request(id="celery-id", retries=0)

        retry_kwargs: dict = {}

        def _fake_retry(**kwargs: object) -> None:
            retry_kwargs.update(kwargs)
            raise Retry()

        with (
            patch.object(run_collector_task, "retry", side_effect=_fake_retry),
            patch(
                "collector.celery_tasks._update_task_schedule_state", new=AsyncMock()
            ) as mock_update,
        ):
            with pytest.raises(Retry):
                task.run({"task": "market-daily-review"})

        task.pop_request()

        assert retry_kwargs["countdown"] == 600
        assert retry_kwargs["max_retries"] == 3
        assert isinstance(retry_kwargs["exc"], ReviewInputDataNotReadyError)
        mock_update.assert_awaited_once()

    @patch("collector.celery_tasks.run_task", new_callable=AsyncMock)
    def test_consecutive_runs_reuse_same_loop(self, mock_run_task: AsyncMock) -> None:
        """同一子进程内的两次任务执行应共享同一个 event loop。"""
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
        """持久化 loop 下，任务之间不应销毁 engine。"""
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
