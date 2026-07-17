from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from collector.scf_handler import (
    _build_task_kwargs,
    _parse_event,
    _run_task,
    main_handler,
)
from collector.tasks import TASK_MAP


@pytest.mark.unit
class TestScfHandler:
    def test_parse_event_dict(self) -> None:
        assert _parse_event({"task": "kline"}) == {"task": "kline"}

    def test_parse_event_json_string(self) -> None:
        assert _parse_event('{"task": "news"}') == {"task": "news"}

    def test_parse_event_plain_string(self) -> None:
        assert _parse_event("auction") == {"task": "auction"}

    def test_parse_event_none(self) -> None:
        assert _parse_event(None) == {}

    def test_build_task_kwargs_kline(self) -> None:
        kwargs = _build_task_kwargs("kline", {"period": "weekly"})
        assert kwargs == {"period": "weekly"}

    def test_build_task_kwargs_financial_report(self) -> None:
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

    @pytest.mark.asyncio
    @pytest.mark.parametrize("task_name", list(TASK_MAP.keys()))
    async def test_run_task_supports_all_tasks(self, task_name: str) -> None:
        mock_result = AsyncMock()
        mock_result.source = "test"
        mock_result.data_type = task_name
        mock_result.status.value = "success"
        mock_result.items_collected = 0
        mock_result.items_stored = 0
        mock_result.errors = []

        mock_task = AsyncMock(return_value=mock_result)
        with patch("collector.scf_handler.TASK_MAP", {task_name: mock_task}):
            result = await _run_task({"task": task_name})

        assert result is mock_result
        mock_task.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_main_handler_success(self) -> None:
        mock_result = AsyncMock()
        mock_result.source = "ths"
        mock_result.data_type = "kline_daily"
        mock_result.status.value = "success"
        mock_result.items_collected = 2
        mock_result.items_stored = 2
        mock_result.errors = []

        with patch("collector.scf_handler._run_task_sync", return_value=mock_result):
            response = main_handler({"task": "kline"}, None)

        assert response["statusCode"] == 200
        body: dict[str, Any] = __import__("json").loads(response["body"])
        assert body["status"] == "success"
        assert body["items_stored"] == 2

    @pytest.mark.asyncio
    async def test_main_handler_failure(self) -> None:
        with patch("collector.scf_handler._run_task_sync", side_effect=ValueError("boom")):
            response = main_handler({"task": "kline"}, None)

        assert response["statusCode"] == 500
        body: dict[str, Any] = __import__("json").loads(response["body"])
        assert body["status"] == "failed"
        assert "boom" in body["error"]
