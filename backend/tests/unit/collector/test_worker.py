"""Unit tests for collector worker loop."""

from unittest.mock import AsyncMock, patch

import pytest

from collector.runtime.worker import WorkerState, _worker_loop


def _make_queue(payloads: list[dict | None], state: WorkerState) -> AsyncMock:
    queue = AsyncMock()
    queue.queue_key = "collector:queue"
    remaining = list(payloads)

    async def _pop(timeout: int = 5) -> dict | None:
        if not remaining:
            state.running = False
            return None
        payload = remaining.pop(0)
        if not remaining:
            state.running = False
        return payload

    queue.pop = AsyncMock(side_effect=_pop)
    return queue


@pytest.mark.unit
class TestCollectorWorker:
    @pytest.mark.asyncio
    async def test_worker_executes_payload_and_stops(self) -> None:
        state = WorkerState()
        queue = _make_queue([{"task": "news", "log_id": 1}], state)

        with (
            patch("collector.runtime.worker.CollectorQueue", return_value=queue),
            patch("collector.runtime.worker.run_task", AsyncMock()) as mock_run,
        ):
            await _worker_loop(state, pop_timeout=1)

        mock_run.assert_awaited_once_with({"task": "news", "log_id": 1})
        queue.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_worker_survives_task_failure(self) -> None:
        state = WorkerState()
        queue = _make_queue([{"task": "news"}, {"task": "kline"}], state)

        with (
            patch("collector.runtime.worker.CollectorQueue", return_value=queue),
            patch(
                "collector.runtime.worker.run_task",
                AsyncMock(side_effect=ValueError("boom")),
            ) as mock_run,
        ):
            await _worker_loop(state, pop_timeout=1)

        assert mock_run.await_count == 2
        queue.close.assert_awaited_once()
