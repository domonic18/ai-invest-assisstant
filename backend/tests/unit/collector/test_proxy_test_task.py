"""代理连通性探测 Celery 任务契约测试。"""

from unittest.mock import MagicMock, patch

import pytest

from collector.celery_tasks import run_proxy_test

pytestmark = pytest.mark.unit


@patch("collector.celery_tasks.CffiSession")
def test_probe_success(mock_session_cls: MagicMock) -> None:
    response = MagicMock(status_code=204)
    mock_session_cls.return_value.__enter__.return_value.get.return_value = response

    result = run_proxy_test("http://175.27.167.123:17890")

    assert result["ok"] is True
    assert result["status_code"] == 204
    assert result["error"] is None
    assert result["latency_ms"] >= 0
    # 代理 URL 同时映射 http/https，探测带超时
    _, kwargs = mock_session_cls.return_value.__enter__.return_value.get.call_args
    assert kwargs["proxies"] == {
        "http": "http://175.27.167.123:17890",
        "https": "http://175.27.167.123:17890",
    }
    assert kwargs["timeout"] == 8.0


@patch("collector.celery_tasks.CffiSession")
def test_probe_non_204_reports_http_status(mock_session_cls: MagicMock) -> None:
    response = MagicMock(status_code=407)
    mock_session_cls.return_value.__enter__.return_value.get.return_value = response

    result = run_proxy_test("http://h:1")

    assert result["ok"] is False
    assert result["status_code"] == 407
    assert result["error"] == "HTTP 407"


@patch("collector.celery_tasks.CffiSession")
def test_probe_connection_error_returns_error_not_raise(
    mock_session_cls: MagicMock,
) -> None:
    mock_session_cls.return_value.__enter__.return_value.get.side_effect = OSError(
        "connection refused"
    )

    result = run_proxy_test("http://dead:1")

    assert result["ok"] is False
    assert result["status_code"] is None
    assert "OSError" in (result["error"] or "")
