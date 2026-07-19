"""Unit tests for the shared EastMoney HTTP client."""

import time
from unittest.mock import MagicMock, patch

import pytest

from collector.core import http_client
from collector.core.http_client import _RateLimiter, eastmoney_get


@pytest.mark.unit
class TestRateLimiter:
    def test_wait_enforces_min_interval(self) -> None:
        limiter = _RateLimiter(min_interval=1.0)
        with (
            patch.object(http_client.time, "sleep") as sleep,
            patch.object(http_client.random, "uniform", return_value=0.0),
        ):
            limiter.wait()  # 首次不等待
            assert sleep.call_count == 0

            limiter.wait()  # 紧接着第二次需要补足间隔
            assert sleep.call_count == 1
            assert 0.9 < sleep.call_args.args[0] <= 1.0

    def test_wait_no_sleep_after_interval(self) -> None:
        limiter = _RateLimiter(min_interval=0.01)
        with patch.object(http_client.random, "uniform", return_value=0.0):
            limiter.wait()
            time.sleep(0.05)
            with patch.object(http_client.time, "sleep") as sleep:
                limiter.wait()
                assert sleep.call_count == 0


@pytest.mark.unit
class TestEastmoneyGet:
    def test_get_applies_default_headers_and_retries(self) -> None:
        response = MagicMock()
        response.raise_for_status.return_value = None
        with (
            patch.object(http_client._limiter, "wait"),
            patch.object(http_client._session, "get", return_value=response) as get,
        ):
            result = eastmoney_get("https://push2.eastmoney.com/api", params={"pn": 1})

        assert result is response
        assert get.call_args.kwargs["params"] == {"pn": 1}
        session_headers = http_client._session.headers
        assert session_headers["Referer"] == "https://data.eastmoney.com/bkzj/hy.html"
        adapter = http_client._session.get_adapter("https://push2.eastmoney.com")
        retry = adapter.max_retries
        assert retry.total == 3
        assert 429 in retry.status_forcelist
        assert 403 not in retry.status_forcelist

    def test_get_raises_for_http_error(self) -> None:
        response = MagicMock()
        response.raise_for_status.side_effect = RuntimeError("boom")
        with (
            patch.object(http_client._limiter, "wait"),
            patch.object(http_client._session, "get", return_value=response),
            pytest.raises(RuntimeError, match="boom"),
        ):
            eastmoney_get("https://push2.eastmoney.com/api")
