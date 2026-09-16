"""服务层单测：参数原样透传、UA 回显、health 永远可答。"""

from typing import Any

import pytest

from app.signer.models import SignResponse
from app.signer.service import SignerService
from app.signer.settings import SignerSettings

pytestmark = pytest.mark.unit

PATH = "/aweme/v1/web/aweme/post/"
JAR = "ttwid=abc; s_v_web_id=xyz"
UA = "Mozilla/5.0 TestUA"


class FakeSlots:
    """SlotManager 鸭子类型桩：脚本化 sign 行为并记录健康计数。"""

    def __init__(
        self,
        results: "list[dict[str, str] | Exception] | None" = None,
        *,
        start_error: Exception | None = None,
    ) -> None:
        self._results = list(results or [])
        self._start_error = start_error
        self.calls: list[tuple[str, str, str, str]] = []

    async def start(self) -> None:
        if self._start_error is not None:
            raise self._start_error

    async def close(self) -> None:
        return None

    async def sign(
        self, cookies: str, user_agent: str, path: str, query: str
    ) -> dict[str, str]:
        self.calls.append((cookies, user_agent, path, query))
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def stats(self) -> dict[str, Any]:
        return {
            "warm_slots": 2,
            "idle": 1,
            "in_use": 0,
            "last_error": "boom" if self._results else None,
        }


def make_service(slots: FakeSlots) -> SignerService:
    return SignerService(slots, SignerSettings())  # type: ignore[arg-type]


class TestSign:
    async def test_params_passthrough_unchanged(self) -> None:
        """SDK 追加参数集原样透传，服务层不得增删任何键。"""
        sdk_params = {
            "a_bogus": "x",
            "verifyFp": "v",
            "fp": "v",
            "uifid": "u",
            "timestamp": "1726473600000",
            "x-secsdk-web-signature": "s",
        }
        service = make_service(FakeSlots([sdk_params]))
        response = await service.sign(PATH, "aid=6383", UA, JAR)
        assert isinstance(response, SignResponse)
        assert response.params == sdk_params
        assert response.user_agent == UA

    async def test_arguments_forwarded_to_slots(self) -> None:
        slots = FakeSlots([{"a_bogus": "x"}])
        service = make_service(slots)
        await service.sign(PATH, "aid=6383&sec=1", UA, JAR)
        assert slots.calls == [(JAR, UA, PATH, "aid=6383&sec=1")]

    async def test_backend_failure_propagates(self) -> None:
        service = make_service(FakeSlots([RuntimeError("slot dead")]))
        with pytest.raises(RuntimeError):
            await service.sign(PATH, "aid=6383", UA, JAR)


class TestHealth:
    def test_ok_reports_slot_stats(self) -> None:
        service = make_service(FakeSlots())
        health = service.health()
        assert health.status == "ok"
        assert health.driver == "playwright"
        assert health.warm_slots == 1
        assert health.in_use == 0

    async def test_unreachable_browser_still_answers(self) -> None:
        """浏览器缺失是启动事实：health 返回 unavailable 而非抛异常。"""
        slots = FakeSlots(start_error=RuntimeError("playwright 未安装（镜像须以 --group signer 构建）"))
        service = make_service(slots)
        await service.start()
        health = service.health()
        assert health.status == "unavailable"
        assert health.last_error is not None
        assert "signer" in health.last_error
