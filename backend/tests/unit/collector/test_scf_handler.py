"""SCF handler 契约测试（事件解析 + 响应包装）。"""

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from collector.runtime.scf_handler import _parse_event, main_handler


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

    @pytest.mark.asyncio
    async def test_main_handler_success(self) -> None:
        mock_result = AsyncMock()
        mock_result.source = "ths"
        mock_result.data_type = "quote_kline_stock_daily"
        mock_result.status.value = "success"
        mock_result.items_collected = 2
        mock_result.items_stored = 2
        mock_result.errors = []

        with patch(
            "collector.runtime.scf_handler.run_task_sync", return_value=mock_result
        ):
            response = main_handler({"task": "kline"}, None)

        assert response["statusCode"] == 200
        body: dict[str, Any] = json.loads(response["body"])
        assert body["status"] == "success"
        assert body["items_stored"] == 2

    @pytest.mark.asyncio
    async def test_main_handler_failure(self) -> None:
        with patch(
            "collector.runtime.scf_handler.run_task_sync",
            side_effect=ValueError("boom"),
        ):
            response = main_handler({"task": "kline"}, None)

        assert response["statusCode"] == 500
        body: dict[str, Any] = json.loads(response["body"])
        assert body["status"] == "failed"
        assert "boom" in body["error"]
