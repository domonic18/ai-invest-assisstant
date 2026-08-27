"""Unit tests for the collector runtime runner (unified execution path)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from collector.core.base import CollectResult, CollectStatus
from collector.runtime.runner import (
    _ERROR_MSG_MAX_LEN,
    _build_task_kwargs,
    _mark_running,
    _persist_error,
    _persist_result,
    run_task,
)


def _make_result() -> CollectResult:
    now = datetime.now(timezone.utc)
    return CollectResult(
        source="cninfo",
        data_type="financial_report",
        status=CollectStatus.SUCCESS,
        items_collected=2,
        items_stored=2,
        errors=[],
        started_at=now,
        finished_at=now,
    )


def _mock_session(mock_log: MagicMock | None) -> MagicMock:
    mock_session = AsyncMock()
    mock_session.get.return_value = mock_log
    return MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_session),
            __aexit__=AsyncMock(return_value=None),
        )
    )


@pytest.mark.unit
class TestBuildTaskKwargs:
    def test_kline(self) -> None:
        kwargs = _build_task_kwargs("kline", {"period": "weekly"})
        assert kwargs == {"period": "weekly"}

    def test_financial_report(self) -> None:
        kwargs = _build_task_kwargs(
            "financial-report",
            {
                "symbols": ["000001"],
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "report_types": ["年报"],
                "preferred_source": "cninfo",
            },
        )
        assert kwargs["symbols"] == ["000001"]
        assert kwargs["start_date"] == "2024-01-01"
        assert kwargs["end_date"] == "2024-12-31"
        assert kwargs["report_types"] == ["年报"]
        assert kwargs["preferred_source"] == "cninfo"

    def test_none_values_are_skipped(self) -> None:
        kwargs = _build_task_kwargs("kline", {"period": None, "symbols": None})
        assert kwargs == {}


@pytest.mark.unit
class TestRunTask:
    @pytest.mark.asyncio
    async def test_run_task_executes_and_persists(self) -> None:
        result = _make_result()
        mock_task = AsyncMock(return_value=result)

        with (
            patch(
                "collector.runtime.runner.TASK_MAP", {"financial-report": mock_task}
            ),
            patch(
                "collector.runtime.runner._persist_result", AsyncMock()
            ) as mock_persist,
        ):
            outcome = await run_task({"task": "financial-report", "log_id": None})

        assert outcome is result
        mock_task.assert_awaited_once()
        (
            task_name,
            log_id,
            celery_task_id,
            task_run_id,
            persisted,
        ) = mock_persist.await_args.args
        assert task_name == "financial-report"
        assert log_id is None
        assert celery_task_id is None
        assert len(task_run_id) == 8
        assert persisted is result

    @pytest.mark.asyncio
    async def test_run_task_marks_running_when_log_id(self) -> None:
        result = _make_result()
        with (
            patch(
                "collector.runtime.runner.TASK_MAP",
                {"financial-report": AsyncMock(return_value=result)},
            ),
            patch(
                "collector.runtime.runner._mark_running", AsyncMock()
            ) as mock_running,
            patch("collector.runtime.runner._persist_result", AsyncMock()),
        ):
            await run_task({"task": "financial-report", "log_id": 7})

        mock_running.assert_awaited_once_with(7)

    @pytest.mark.asyncio
    async def test_unknown_task_raises_and_persists_error(self) -> None:
        with patch(
            "collector.runtime.runner._persist_error", AsyncMock()
        ) as mock_error:
            with pytest.raises(ValueError, match="Unknown task"):
                await run_task({"task": "nope", "log_id": 9})

        mock_error.assert_awaited_once()
        assert mock_error.await_args.args[0] == 9

    @pytest.mark.asyncio
    async def test_missing_task_raises(self) -> None:
        with pytest.raises(ValueError, match="Missing required field"):
            await run_task({})


@pytest.mark.unit
class TestLogPersistence:
    @pytest.mark.asyncio
    async def test_mark_running(self) -> None:
        mock_log = MagicMock()
        with patch(
            "collector.runtime.runner.AsyncSessionLocal",
            _mock_session(mock_log),
        ):
            await _mark_running(1)

        assert mock_log.status == "running"
        assert isinstance(mock_log.started_at, datetime)

    @pytest.mark.asyncio
    async def test_persist_result_updates_existing_row(self) -> None:
        mock_log = MagicMock()
        mock_log.meta = {"task": "financial-report"}
        mock_session = AsyncMock()
        mock_session.get.return_value = mock_log
        session_factory = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_session),
                __aexit__=AsyncMock(return_value=None),
            )
        )

        with patch(
            "collector.runtime.runner.AsyncSessionLocal", session_factory
        ):
            await _persist_result(
                "financial-report", 1, None, "abcd1234", _make_result()
            )

        assert mock_log.status == "success"
        assert mock_log.source == "cninfo"
        assert mock_log.records_count == 2
        assert mock_log.meta["task_run_id"] == "abcd1234"
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_persist_result_inserts_row_without_log_id(self) -> None:
        mock_session = MagicMock()
        mock_session.commit = AsyncMock()
        session_factory = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_session),
                __aexit__=AsyncMock(return_value=None),
            )
        )

        with patch(
            "collector.runtime.runner.AsyncSessionLocal", session_factory
        ):
            await _persist_result(
                "financial-report", None, None, "abcd1234", _make_result()
            )

        mock_session.add.assert_called_once()
        added = mock_session.add.call_args.args[0]
        assert added.task_name == "financial-report"
        assert added.status == "success"
        assert added.meta["task_run_id"] == "abcd1234"
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_persist_error_records_traceback_truncated(self) -> None:
        mock_log = MagicMock()
        with patch(
            "collector.runtime.runner.AsyncSessionLocal",
            _mock_session(mock_log),
        ):
            try:
                raise ValueError("x" * 10000)
            except ValueError as exc:
                await _persist_error(1, None, exc)

        assert mock_log.status == "failed"
        assert "ValueError" in mock_log.error_msg
        assert "Traceback" in mock_log.error_msg
        assert len(mock_log.error_msg) <= _ERROR_MSG_MAX_LEN
