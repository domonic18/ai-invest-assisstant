"""Unit tests for collector worker."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from collector.base import CollectResult, CollectStatus
from collector.worker import _execute_payload, _update_log_result, _update_log_running


@pytest.mark.unit
class TestCollectorWorker:
    @pytest.mark.asyncio
    async def test_update_log_running(self) -> None:
        mock_log = MagicMock()
        mock_session = AsyncMock()
        mock_session.get.return_value = mock_log

        with patch(
            "collector.worker.AsyncSessionLocal",
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_session),
                __aexit__=AsyncMock(return_value=None),
            ),
        ):
            await _update_log_running(1)

        assert mock_log.status == "running"
        assert isinstance(mock_log.started_at, datetime)
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_log_result(self) -> None:
        mock_log = MagicMock()
        mock_session = AsyncMock()
        mock_session.get.return_value = mock_log
        result = CollectResult(
            source="cninfo",
            data_type="financial_report",
            status=CollectStatus.SUCCESS,
            items_collected=2,
            items_stored=2,
            errors=[],
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
        )

        with patch(
            "collector.worker.AsyncSessionLocal",
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_session),
                __aexit__=AsyncMock(return_value=None),
            ),
        ):
            await _update_log_result(1, result)

        assert mock_log.status == "success"
        assert mock_log.source == "cninfo"
        assert mock_log.records_count == 2
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_payload_updates_log(self) -> None:
        result = CollectResult(
            source="cninfo",
            data_type="financial_report",
            status=CollectStatus.SUCCESS,
            items_collected=1,
            items_stored=1,
            errors=[],
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
        )

        with (
            patch("collector.worker._update_log_running", AsyncMock()) as mock_running,
            patch("collector.worker._update_log_result", AsyncMock()) as mock_result,
            patch("collector.worker._run_task", AsyncMock(return_value=result)),
        ):
            await _execute_payload({"task": "financial-report", "log_id": 7})

        mock_running.assert_awaited_once_with(7)
        mock_result.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_payload_handles_failure(self) -> None:
        with (
            patch("collector.worker._update_log_running", AsyncMock()) as mock_running,
            patch("collector.worker._update_log_error", AsyncMock()) as mock_error,
            patch("collector.worker._run_task", AsyncMock(side_effect=ValueError("boom"))),
        ):
            await _execute_payload({"task": "financial-report", "log_id": 8})

        mock_running.assert_awaited_once_with(8)
        mock_error.assert_awaited_once()
