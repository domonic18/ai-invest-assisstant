"""Playwright SEAM：本服务唯一知道浏览器存在的模块。

playwright 依赖收在 uv ``signer`` 组；import 全部收敛在函数内，
dev 环境不装该组时 mypy/pytest/collector 均不受影响。
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog

from app.signer.settings import SignerSettings
from app.signer.shim import (
    CAPTURE_INIT_SCRIPT,
    CHROMIUM_ARGS,
    READY_MAX_CONSECUTIVE_ERRORS,
    READY_POLL_GROWTH,
    READY_POLL_MAX_SECONDS,
    READY_POLL_SECONDS,
    SIGN_SCRIPT,
)

logger = structlog.get_logger(__name__)


class SignPageError(RuntimeError):
    """签名页内操作失败（SDK 未就绪/页面崩溃/evaluate 异常）——丢弃 slot 可重试。"""


class BrowserUnavailableError(RuntimeError):
    """浏览器驱动缺失或未启动——镜像构建/启动问题，重启前不会自愈。"""


class SigningContext:
    """一个持着 douyin.com 页面的 warm 浏览器上下文（绑定单一 jar）。"""

    def __init__(
        self,
        context: Any,
        page: Any,
        settings: SignerSettings,
        *,
        clock: Any = time.monotonic,
    ) -> None:
        self._context = context
        self._page = page
        self._settings = settings
        self._clock = clock
        self._closed = False

    async def wait_ready(self) -> None:
        """就绪探测：用一次性 query 试签名直到 SDK 开始追加参数。

        页面导航可完成远早于 security bundle 就绪，那个窗口内签名只会得到
        「SDK added nothing」——像算法变更，实为急躁。探测本身走真签名路径，
        指数退避防探崩（常量见 shim.py）。
        """
        deadline = self._clock() + self._settings.sdk_ready_timeout_seconds
        delay = READY_POLL_SECONDS
        consecutive_errors = 0
        while self._clock() < deadline:
            try:
                await self.sign("/aweme/v1/web/aweme/post/", "probe=1")
                return
            except SignPageError:
                consecutive_errors += 1
                if consecutive_errors >= READY_MAX_CONSECUTIVE_ERRORS:
                    raise SignPageError("签名页面连续无响应，判定已崩溃")
            await asyncio.sleep(min(delay, READY_POLL_MAX_SECONDS))
            delay *= READY_POLL_GROWTH
        raise SignPageError("签名页面就绪探测超时（security bundle 未加载）")

    async def sign(self, path: str, query: str) -> dict[str, str]:
        """请页面 SDK 签一次请求，返回它追加的参数（原样，不增不删）。"""
        if self._closed:
            raise SignPageError("signing context is closed")
        try:
            result = await self._page.evaluate(
                SIGN_SCRIPT,
                {"url": f"https://www.douyin.com{path}", "query": query, "method": "GET"},
            )
        except Exception as exc:
            raise SignPageError(f"签名脚本执行失败: {exc}") from exc
        if not isinstance(result, dict) or result.get("error"):
            reason = result.get("error", "no result") if isinstance(result, dict) else "no result"
            raise SignPageError(f"页面 SDK 未产出签名（{reason}）")
        params = result.get("params")
        if not isinstance(params, dict) or not params:
            raise SignPageError("页面 SDK 未追加任何参数")
        return {str(k): str(v) for k, v in params.items()}

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            await self._context.close()
        except Exception as exc:
            logger.warning("signer.context_close_failed", error=str(exc))


class PlaywrightBackend:
    """浏览器进程持有者：start 只 launch 进程，context 按需打开。"""

    def __init__(self, settings: SignerSettings) -> None:
        self._settings = settings
        self._pw: Any = None
        self._browser: Any = None
        self._version: str | None = None

    async def start(self) -> None:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise BrowserUnavailableError(
                "playwright 未安装（镜像须以 --group signer 构建）"
            ) from exc
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            headless=self._settings.headless, args=list(CHROMIUM_ARGS)
        )
        self._version = getattr(self._pw, "__version__", None)
        logger.info("signer.browser_started", version=self._version)

    async def close(self) -> None:
        for closer in (self._browser, self._pw):
            if closer is not None:
                try:
                    await closer.close()
                except Exception as exc:
                    logger.warning("signer.browser_close_failed", error=str(exc))
        self._browser = None
        self._pw = None

    @property
    def version(self) -> str | None:
        return self._version

    @property
    def started(self) -> bool:
        return self._browser is not None

    async def open_signing_context(
        self, cookies: list[dict[str, str]], user_agent: str
    ) -> SigningContext:
        """以调用方身份开一个签名上下文。

        UA/locale/时区在 context 级设定（页面先报一个再改另一个为时已晚）；
        cookie 必须在 goto 前装入、init script 必须在任何页面脚本前挂上——
        SDK 在文档加载时读一次 s_v_web_id 并缓存，warm 页上换 jar 无效。
        """
        if not self.started:
            raise BrowserUnavailableError("browser 未启动")
        try:
            context = await self._browser.new_context(
                user_agent=user_agent,
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
            )
            await context.add_cookies(cookies)
            page = await context.new_page()
            await page.add_init_script(CAPTURE_INIT_SCRIPT)
            await page.goto(
                self._settings.signing_page_url,
                wait_until="domcontentloaded",
                timeout=self._settings.context_open_timeout_seconds * 1000,
            )
        except Exception as exc:
            raise SignPageError(f"签名上下文打开失败: {exc}") from exc
        return SigningContext(context, page, self._settings)
