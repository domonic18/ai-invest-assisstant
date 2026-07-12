"""Collector request middleware: rate limiting, proxy rotation, cookies, UA."""

import asyncio
import random
from collections import defaultdict
from typing import Any

UA_LIST = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]


class RateLimiter:
    """简单异步令牌桶限速器。"""

    def __init__(self, rate: float = 1.0, max_tokens: float = 2.0):
        self.rate = rate
        self.max_tokens = max_tokens
        self.tokens = max_tokens
        self.last_update = asyncio.get_event_loop().time()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self.last_update
            self.tokens = min(self.max_tokens, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens < 1.0:
                wait = (1.0 - self.tokens) / self.rate
                await asyncio.sleep(wait)
                self.tokens = 0.0
            else:
                self.tokens -= 1.0


class RequestMiddleware:
    """请求中间件：限速、代理、Cookie、User-Agent。"""

    def __init__(self, proxies: list[str] | None = None, cookies: dict[str, str] | None = None):
        self.proxies = proxies or []
        self.cookies = cookies or {}
        self._rate_limiters: dict[str, RateLimiter] = defaultdict(lambda: RateLimiter())

    async def process(self, request: dict[str, Any], source: str = "default") -> dict[str, Any]:
        headers = request.setdefault("headers", {})

        # 1. 限速
        await self._rate_limiters[source].acquire()

        # 2. 随机 User-Agent
        headers["User-Agent"] = random.choice(UA_LIST)

        # 3. 代理轮换
        if self.proxies:
            request["proxy"] = random.choice(self.proxies)

        # 4. Cookie 注入
        if source in self.cookies:
            headers["Cookie"] = self.cookies[source]

        return request
