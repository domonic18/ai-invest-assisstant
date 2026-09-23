"""网络层超时兜底契约测试：requests 默认超时注入与 run_in_thread 等待上限。"""

import asyncio
import time
from typing import Any

import pytest
import requests

from collector.core import net_timeout
from collector.core.net_timeout import patch_requests_default_timeout


def _install_probe(monkeypatch: pytest.MonkeyPatch, captured: dict[str, Any]) -> None:
    """把 Session.request 换成记录 kwargs 即抛错的 probe，并打上补丁。"""

    def probe(self: requests.Session, method: str, url: str, **kwargs: Any) -> Any:
        captured.update(kwargs)
        raise RuntimeError("stop-before-network")

    # 模块级 _original_request 缓存复位，使补丁捕获 probe 而非真实实现
    monkeypatch.setattr(net_timeout, "_original_request", None)
    monkeypatch.setattr(requests.Session, "request", probe)
    patch_requests_default_timeout(30)


@pytest.mark.unit
class TestPatchRequestsDefaultTimeout:
    def test_injects_default_timeout_when_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, Any] = {}
        _install_probe(monkeypatch, captured)

        with pytest.raises(RuntimeError, match="stop-before-network"):
            requests.Session().request("GET", "https://example.com")

        assert captured["timeout"] == 30

    def test_explicit_timeout_not_overridden(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, Any] = {}
        _install_probe(monkeypatch, captured)

        with pytest.raises(RuntimeError, match="stop-before-network"):
            requests.Session().request("GET", "https://example.com", timeout=(5, 10))

        assert captured["timeout"] == (5, 10)

    def test_top_level_get_goes_through_session_wrapper(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """requests.get 顶层 API 内部走 Session.request，同样被兜底覆盖。"""
        captured: dict[str, Any] = {}
        _install_probe(monkeypatch, captured)

        with pytest.raises(RuntimeError, match="stop-before-network"):
            requests.get("https://example.com")

        assert captured["timeout"] == 30


@pytest.mark.unit
class TestRunInThreadTimeout:
    async def test_timeout_raises_and_does_not_block_loop(self) -> None:
        from collector.core.async_helpers import run_in_thread

        def slow() -> None:
            time.sleep(5)

        start = time.monotonic()
        with pytest.raises(TimeoutError):
            await run_in_thread(slow, timeout=0.1)
        assert time.monotonic() - start < 2

    async def test_no_timeout_waits_for_result(self) -> None:
        from collector.core.async_helpers import run_in_thread

        def quick() -> int:
            return 42

        assert await run_in_thread(quick) == 42

    async def test_timeout_kwarg_not_forwarded_to_func(self) -> None:
        from collector.core.async_helpers import run_in_thread

        def accept_kwargs(**kwargs: object) -> dict[str, object]:
            return kwargs

        assert await run_in_thread(accept_kwargs, a=1, timeout=5) == {"a": 1}


@pytest.mark.unit
class TestAsyncioWaitForSemantics:
    async def test_timeout_error_type_is_asyncio_timeout(self) -> None:
        """asyncio.wait_for 抛的即内建 TimeoutError（py3.11+ 与 asyncio.TimeoutError 同类）。"""
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(asyncio.sleep(1), 0.01)
