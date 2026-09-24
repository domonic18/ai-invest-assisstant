"""槽位池单测：fake 页面/后端驱动，覆盖绑定命中、LRU 重建、过期刷新与失败重开。

就绪探测（wait_ready 的 probe query）与真实签名在 FakePage 上解耦：
probe 恒返回成功，脚本化结果队列只服务真实签名——测试不触碰真实退避睡眠。
"""

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.signer.backend import SigningContext, SignPageError
from app.signer.settings import SignerSettings
from app.signer.slots import SlotManager, binding_key

pytestmark = pytest.mark.unit

JAR_A = "ttwid=aaa; s_v_web_id=x1"
JAR_B = "ttwid=bbb; s_v_web_id=x2"
UA = "Mozilla/5.0 TestUA"
PATH = "/aweme/v1/web/aweme/post/"

_OK = {"params": {"a_bogus": "sig"}}


def make_context(
    results: "list[dict[str, Any] | Exception]", *, sign_delay: float = 0.0
) -> SigningContext:
    """真实 SigningContext 壳 + fake page/context：按序回结果或抛异常。"""

    class FakePage:
        def __init__(self) -> None:
            self._results = list(results)

        async def evaluate(self, script: str, payload: dict[str, Any]) -> Any:
            if payload.get("query") == "probe=1":
                return _OK  # 就绪探测恒成功：页面即视为已就绪
            if sign_delay:
                await asyncio.sleep(sign_delay)
            result = self._results.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

    browser_context = SimpleNamespace(close=AsyncMock())
    return SigningContext(browser_context, FakePage(), SignerSettings())


class FakeBackend:
    def __init__(self, contexts: "list[SigningContext]") -> None:
        self._contexts = list(contexts)
        self.opened = 0
        self.started = False
        self.closed = False
        self.last_cookies: list[dict[str, str]] | None = None
        self.last_ua: str | None = None

    async def start(self) -> None:
        self.started = True

    async def close(self) -> None:
        self.closed = True

    async def open_signing_context(
        self, cookies: list[dict[str, str]], user_agent: str
    ) -> SigningContext:
        self.opened += 1
        self.last_cookies = cookies
        self.last_ua = user_agent
        return self._contexts.pop(0)


def make_manager(
    backend: FakeBackend, settings: SignerSettings | None = None, *, clock: Any = None
) -> SlotManager:
    kwargs: dict[str, Any] = {}
    if clock is not None:
        kwargs["clock"] = clock
    return SlotManager(backend, settings or SignerSettings(), **kwargs)


class TestBindingKey:
    def test_stable_and_identity_sensitive(self) -> None:
        assert binding_key(JAR_A, UA) == binding_key(JAR_A, UA)
        assert binding_key(JAR_A, UA) != binding_key(JAR_A, "Other/UA")
        assert binding_key(JAR_A, UA) != binding_key(JAR_B, UA)
        assert len(binding_key(JAR_A, UA)) == 16


class TestSlotLifecycle:
    async def test_binding_hit_reuses_warm_context(self) -> None:
        backend = FakeBackend([make_context([_OK, _OK]), make_context([])])
        manager = make_manager(backend)
        first = await manager.sign(JAR_A, UA, PATH, "aid=6383")
        second = await manager.sign(JAR_A, UA, PATH, "aid=6383")
        assert first == second == {"a_bogus": "sig"}
        assert backend.opened == 1

    async def test_capacity_one_evicts_lru_on_new_binding(self) -> None:
        settings = SignerSettings(warm_slots=1)
        first_ctx = make_context([_OK])
        second_ctx = make_context([_OK])
        backend = FakeBackend([first_ctx, second_ctx])
        manager = make_manager(backend, settings)
        await manager.sign(JAR_A, UA, PATH, "aid=1")
        await manager.sign(JAR_B, UA, PATH, "aid=2")
        assert backend.opened == 2
        first_ctx._context.close.assert_awaited()

    async def test_expired_slot_is_rebuilt(self) -> None:
        settings = SignerSettings(warm_slots=2, warm_refresh_seconds=100.0)
        now = 1000.0
        backend = FakeBackend([make_context([_OK]), make_context([_OK])])
        manager = make_manager(backend, settings, clock=lambda: now)
        await manager.sign(JAR_A, UA, PATH, "aid=1")
        now += 101.0
        await manager.sign(JAR_A, UA, PATH, "aid=2")
        assert backend.opened == 2

    async def test_cookies_parsed_for_backend(self) -> None:
        backend = FakeBackend([make_context([_OK])])
        manager = make_manager(backend)
        await manager.sign(f"{JAR_A}; broken", UA, PATH, "aid=1")
        assert backend.last_cookies is not None
        assert [c["name"] for c in backend.last_cookies] == ["ttwid", "s_v_web_id"]
        assert backend.last_ua == UA

    async def test_stats_reflect_pool(self) -> None:
        backend = FakeBackend([make_context([_OK])])
        manager = make_manager(backend)
        assert manager.stats() == {
            "warm_slots": 2,
            "idle": 0,
            "in_use": 0,
            "last_error": None,
        }
        await manager.sign(JAR_A, UA, PATH, "aid=1")
        stats = manager.stats()
        assert stats["idle"] == 1
        assert stats["in_use"] == 0


class TestFailureSemantics:
    async def test_failure_discards_and_succeeds_on_fresh_context(self) -> None:
        contexts = [
            make_context([SignPageError("the SDK added nothing")]),
            make_context([_OK]),
        ]
        backend = FakeBackend(contexts)
        manager = make_manager(backend)
        params = await manager.sign(JAR_A, UA, PATH, "aid=1")
        assert params == {"a_bogus": "sig"}
        assert backend.opened == 2
        assert "the SDK added nothing" in (manager.stats()["last_error"] or "")

    async def test_two_consecutive_failures_raise(self) -> None:
        failure = SignPageError("page crashed")
        backend = FakeBackend(
            [make_context([failure, failure]), make_context([failure, failure])]
        )
        manager = make_manager(backend, SignerSettings(sign_attempts_per_request=2))
        with pytest.raises(SignPageError):
            await manager.sign(JAR_A, UA, PATH, "aid=1")
        assert backend.opened == 2
        stats = manager.stats()
        assert stats["idle"] == 0 and stats["in_use"] == 0

    async def test_timeout_treated_as_failure_with_retry(self) -> None:
        settings = SignerSettings(sign_timeout_seconds=0.01)
        backend = FakeBackend(
            [make_context([_OK], sign_delay=0.5), make_context([_OK])]
        )
        manager = make_manager(backend, settings)
        params = await manager.sign(JAR_A, UA, PATH, "aid=1")
        assert params == {"a_bogus": "sig"}
        assert "超时" in (manager.stats()["last_error"] or "")


class TestManagerDelegation:
    async def test_start_close_delegate(self) -> None:
        backend = FakeBackend([make_context([_OK])])
        manager = make_manager(backend)
        await manager.start()
        assert backend.started
        await manager.sign(JAR_A, UA, PATH, "aid=1")
        await manager.close()
        assert backend.closed
        assert manager.stats()["idle"] == 0

    async def test_concurrent_signs_do_not_exceed_capacity(self) -> None:
        settings = SignerSettings(warm_slots=2)
        backend = FakeBackend([make_context([_OK, _OK]), make_context([_OK, _OK])])
        manager = make_manager(backend, settings)
        jars = [JAR_A, JAR_B, JAR_A, JAR_B]
        results = await asyncio.gather(
            *[manager.sign(jar, UA, PATH, f"aid={i}") for i, jar in enumerate(jars)]
        )
        assert all(r == {"a_bogus": "sig"} for r in results)
        assert backend.opened <= 2
        stats = manager.stats()
        assert stats["in_use"] == 0
