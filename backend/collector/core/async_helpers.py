"""Helpers for running synchronous code without blocking the asyncio event loop.

Many third-party libraries used by collectors (akshare, requests, pandas,
pypdf, minio) are synchronous.  Wrapping their calls in a thread pool keeps the
event loop responsive when running inside an async worker, CLI, or SCF handler.
"""

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any

_executor: ThreadPoolExecutor | None = None

DEFAULT_MAX_WORKERS = 4


def get_executor(max_workers: int = DEFAULT_MAX_WORKERS) -> ThreadPoolExecutor:
    """Return the process-level thread pool executor, creating it if needed."""
    global _executor  # noqa: PLW0603
    if _executor is None:
        _executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="collector_sync",
        )
    return _executor


async def run_in_thread(func: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
    """Run ``func(*args, **kwargs)`` in a thread pool and await the result."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(get_executor(), partial(func, *args, **kwargs))


async def to_thread(func: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
    """Alias for ``asyncio.to_thread`` when available, otherwise ``run_in_thread``."""
    if hasattr(asyncio, "to_thread"):
        return await asyncio.to_thread(func, *args, **kwargs)
    return await run_in_thread(func, *args, **kwargs)
