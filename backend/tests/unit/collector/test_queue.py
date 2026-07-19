"""Unit tests for collector Redis queue and dispatcher."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from collector.runtime.dispatcher import dispatch_collector_task
from collector.runtime.queue import CollectorQueue


@pytest.mark.unit
class TestCollectorQueue:
    @pytest.mark.asyncio
    async def test_push_serializes_payload(self) -> None:
        mock_client = AsyncMock()
        mock_client.lpush.return_value = 1
        queue = CollectorQueue(redis_url="redis://localhost:6379/0")
        queue._client = mock_client

        length = await queue.push({"task": "kline", "symbols": ["000001"]})

        assert length == 1
        mock_client.lpush.assert_awaited_once()
        args = mock_client.lpush.await_args.args
        assert args[0] == "collector:queue"
        assert '"task": "kline"' in args[1]

    @pytest.mark.asyncio
    async def test_pop_deserializes_payload(self) -> None:
        mock_client = AsyncMock()
        mock_client.brpop.return_value = ("collector:queue", '{"task": "news"}')
        queue = CollectorQueue(redis_url="redis://localhost:6379/0")
        queue._client = mock_client

        payload = await queue.pop(timeout=5)

        assert payload == {"task": "news"}
        mock_client.brpop.assert_awaited_once_with("collector:queue", timeout=5)

    @pytest.mark.asyncio
    async def test_pop_returns_none_on_timeout(self) -> None:
        mock_client = AsyncMock()
        mock_client.brpop.return_value = None
        queue = CollectorQueue(redis_url="redis://localhost:6379/0")
        queue._client = mock_client

        payload = await queue.pop(timeout=5)

        assert payload is None


@pytest.mark.unit
class TestCollectorDispatcher:
    @pytest.mark.asyncio
    async def test_dispatch_creates_log_and_pushes_payload(self) -> None:
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_log = MagicMock()
        mock_log.id = 5

        with (
            patch("collector.runtime.dispatcher.CollectorLog", return_value=mock_log),
            patch.object(
                CollectorQueue,
                "push",
                AsyncMock(return_value=1),
            ) as mock_push,
        ):
            log = await dispatch_collector_task(
                session=mock_session,
                task_name="financial-report",
                params={"preferred_source": "cninfo"},
            )

        assert log is mock_log
        mock_push.assert_awaited_once()
        payload = mock_push.await_args.args[0]
        assert payload["task"] == "financial-report"
        assert payload["log_id"] == 5
        assert payload["preferred_source"] == "cninfo"
        mock_session.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_dispatch_marks_log_failed_when_push_fails(self) -> None:
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_log = MagicMock()

        with (
            patch("collector.runtime.dispatcher.CollectorLog", return_value=mock_log),
            patch.object(
                CollectorQueue,
                "push",
                AsyncMock(side_effect=ConnectionError("redis down")),
            ),
        ):
            with pytest.raises(ConnectionError):
                await dispatch_collector_task(
                    session=mock_session,
                    task_name="kline",
                    params={},
                )

        assert mock_log.status == "failed"
        assert "redis down" in mock_log.error_msg
        mock_session.commit.assert_awaited()
