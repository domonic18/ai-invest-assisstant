"""warm 签名槽位池：按 (jar, UA) 绑定上下文，LRU 容量管理。

实测约束（来源 cloak.py，2026-09）：签名与身份绑定——verifyFp 取自文档
加载时的 s_v_web_id cookie，warm 页面上换 jar 无效，必须新文档；
平台常发新 JS，超过 ``warm_refresh_seconds`` 的旧页签出旧参数。
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass
from typing import Any, Protocol

import structlog

from app.signer.backend import SigningContext, SignPageError
from app.signer.settings import SignerSettings
from app.signer.validation import parse_cookie_header

logger = structlog.get_logger(__name__)


class SigningBackend(Protocol):
    """PlaywrightBackend 的鸭子类型（测试注入 fake backend）。"""

    async def start(self) -> None: ...

    async def close(self) -> None: ...

    async def open_signing_context(
        self, cookies: list[dict[str, str]], user_agent: str
    ) -> SigningContext: ...


def binding_key(cookies: str, user_agent: str) -> str:
    """槽位绑定键：cookie 是凭据，只允许摘要进日志/统计。"""
    return hashlib.sha256(f"{user_agent}|{cookies}".encode()).hexdigest()[:16]


@dataclass
class _Slot:
    binding: str
    context: SigningContext
    created_at: float


class SlotManager:
    """idle 池 + busy 计数（含创建中），容量 = idle + busy ≤ warm_slots。"""

    def __init__(
        self,
        backend: SigningBackend,
        settings: SignerSettings,
        *,
        clock: Any = time.monotonic,
    ) -> None:
        self._backend = backend
        self._settings = settings
        self._clock = clock
        self._idle: list[_Slot] = []
        self._busy = 0
        self._cond = asyncio.Condition()
        self._last_error: str | None = None

    async def start(self) -> None:
        """prewarm 语义：只 launch 浏览器进程（jar 绑定 context 无法预知）。"""
        await self._backend.start()

    async def close(self) -> None:
        for slot in self._idle:
            await slot.context.close()
        self._idle.clear()
        await self._backend.close()

    def stats(self) -> dict[str, Any]:
        return {
            "warm_slots": self._settings.warm_slots,
            "idle": len(self._idle),
            "in_use": self._busy,
            "last_error": self._last_error,
        }

    async def sign(
        self, cookies: str, user_agent: str, path: str, query: str
    ) -> dict[str, str]:
        """签名；失败丢弃 slot 用全新文档重试，两次仍败则向上抛。"""
        binding = binding_key(cookies, user_agent)
        last_exc: SignPageError | None = None
        for _ in range(self._settings.sign_attempts_per_request):
            try:
                slot = await self._acquire(cookies, user_agent, binding)
            except SignPageError as exc:
                self._record_error(str(exc))
                last_exc = exc
                continue
            try:
                async with asyncio.timeout(self._settings.sign_timeout_seconds):
                    params = await slot.context.sign(path, query)
            except SignPageError as exc:
                self._record_error(str(exc))
                last_exc = exc
            except TimeoutError:
                message = f"签名超时（{self._settings.sign_timeout_seconds}s）"
                self._record_error(message)
                last_exc = SignPageError(message)
            else:
                await self._release(slot)
                return params
            await self._discard(slot)
        assert last_exc is not None
        raise last_exc

    async def _acquire(self, cookies: str, user_agent: str, binding: str) -> _Slot:
        acquired: _Slot | None = None
        to_close: list[_Slot] = []
        try:
            async with self._cond:
                while True:
                    index = self._index_of(binding)
                    if index is not None:
                        slot = self._idle.pop(index)
                        if (
                            self._clock() - slot.created_at
                            <= self._settings.warm_refresh_seconds
                        ):
                            self._busy += 1
                            acquired = slot
                            break
                        to_close.append(slot)  # 过期页签旧参数，必须重建
                        continue
                    if len(self._idle) + self._busy < self._settings.warm_slots:
                        self._busy += 1  # 创建中的 context 也占容量
                        break
                    if self._idle:
                        to_close.append(self._idle.pop(0))  # LRU 淘汰
                        self._busy += 1
                        break
                    await self._cond.wait()
            for slot in to_close:
                await slot.context.close()
            if acquired is None:
                acquired = await self._create(cookies, user_agent, binding)
            return acquired
        except BaseException:
            async with self._cond:
                self._busy -= 1
                self._cond.notify_all()
            raise

    def _index_of(self, binding: str) -> int | None:
        for index in range(len(self._idle) - 1, -1, -1):
            if self._idle[index].binding == binding:
                return index
        return None

    async def _create(self, cookies: str, user_agent: str, binding: str) -> _Slot:
        parsed = parse_cookie_header(cookies)
        context = await self._backend.open_signing_context(parsed, user_agent)
        slot = _Slot(binding=binding, context=context, created_at=self._clock())
        try:
            await context.wait_ready()
        except SignPageError:
            await context.close()
            raise
        logger.info("signer.slot_ready", binding=binding)
        return slot

    async def _finish(self, slot: _Slot, *, reuse: bool) -> None:
        async with self._cond:
            self._busy -= 1
            if reuse:
                self._idle.append(slot)
            self._cond.notify_all()
        if not reuse:
            await slot.context.close()

    async def _release(self, slot: _Slot) -> None:
        await self._finish(slot, reuse=True)

    async def _discard(self, slot: _Slot) -> None:
        await self._finish(slot, reuse=False)

    def _record_error(self, message: str) -> None:
        self._last_error = message
        logger.warning("signer.sign_failed", error=message)
