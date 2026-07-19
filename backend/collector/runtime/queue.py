"""Redis queue client for collector task dispatching.

The web API pushes serialized task payloads to a Redis list; the collector
worker polls the same list with BLPOP and executes the task.
"""

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from collector.core.config import collector_queue_key
from collector.core.config import redis_url as default_redis_url

logger = logging.getLogger(__name__)

DEFAULT_QUEUE_KEY = collector_queue_key


class CollectorQueue:
    """Async Redis queue for collector task payloads."""

    def __init__(
        self,
        redis_url: str | None = None,
        queue_key: str | None = None,
    ) -> None:
        self.redis_url = redis_url or default_redis_url
        self.queue_key = queue_key or DEFAULT_QUEUE_KEY
        self._client: aioredis.Redis | None = None

    async def _get_client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = aioredis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_timeout=None,
                socket_connect_timeout=10,
            )
        return self._client

    async def push(self, payload: dict[str, Any]) -> int:
        """Push a task payload to the queue. Returns the new queue length."""
        client = await self._get_client()
        data = json.dumps(payload, ensure_ascii=False)
        length = await client.lpush(self.queue_key, data)
        logger.info(
            "collector_task_queued: queue=%s task=%s",
            self.queue_key,
            payload.get("task"),
        )
        return int(length)

    async def pop(self, timeout: int = 5) -> dict[str, Any] | None:
        """Blocking pop from the queue. Returns payload or None on timeout."""
        client = await self._get_client()
        result = await client.brpop(self.queue_key, timeout=timeout)
        if result is None:
            return None
        _, data = result
        payload: dict[str, Any] = json.loads(data)
        logger.info(
            "collector_task_popped: queue=%s task=%s",
            self.queue_key,
            payload.get("task"),
        )
        return payload

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "CollectorQueue":
        await self._get_client()
        return self

    async def __aexit__(self, *args: Any, **kwargs: Any) -> None:
        await self.close()


async def push_task(payload: dict[str, Any], queue_key: str | None = None) -> int:
    """Convenience helper to push a single task payload."""
    queue = CollectorQueue(queue_key=queue_key)
    return await queue.push(payload)
