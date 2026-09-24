"""签名服务决策层：无 HTTP 依赖，可直接单测。

路由层零决策（parse → service → shape reply）；SDK 追加参数在此
原样透传——任何"补一个常见参数"的善意修正都是签名伪造
（a_bogus 覆盖精确 query 串，补参 = 403 Sign Invalid，上游事故记录）。
"""

from __future__ import annotations

import structlog

from app.signer.models import HealthResponse, SignResponse
from app.signer.settings import SignerSettings
from app.signer.slots import SlotManager

logger = structlog.get_logger(__name__)


class SignerService:
    def __init__(self, slots: SlotManager, settings: SignerSettings) -> None:
        self._slots = slots
        self._settings = settings
        self._start_error: str | None = None

    async def start(self) -> None:
        """lifespan 入口：浏览器缺失记录为启动事实而非 crash（/health 可答）。"""
        try:
            await self._slots.start()
        except Exception as exc:
            self._start_error = str(exc)[:300]
            logger.error("signer.start_failed", error=self._start_error)

    async def close(self) -> None:
        await self._slots.close()

    async def sign(
        self, path: str, query: str, user_agent: str, cookies: str
    ) -> SignResponse:
        params = await self._slots.sign(cookies, user_agent, path, query)
        return SignResponse(params=params, user_agent=user_agent)

    def health(self) -> HealthResponse:
        stats = self._slots.stats()
        base = {
            "warm_slots": stats["idle"],
            "in_use": stats["in_use"],
            "last_error": stats["last_error"] or self._start_error,
        }
        if self._start_error is not None:
            return HealthResponse(status="unavailable", **base)
        return HealthResponse(status="ok", driver="playwright", **base)
