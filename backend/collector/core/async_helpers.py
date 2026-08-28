"""在不阻塞 asyncio 事件循环的前提下运行同步代码的辅助函数。

采集器使用的许多第三方库（akshare、requests、pandas、pypdf、minio）都是
同步的。把它们的调用包装进线程池，可以让事件循环在 async worker、CLI 或
SCF handler 中运行时保持响应。
"""

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any

_executor: ThreadPoolExecutor | None = None

DEFAULT_MAX_WORKERS = 4


def get_executor(max_workers: int = DEFAULT_MAX_WORKERS) -> ThreadPoolExecutor:
    """返回进程级共享线程池执行器，必要时创建。"""
    global _executor  # noqa: PLW0603
    if _executor is None:
        _executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="collector_sync",
        )
    return _executor


async def run_in_thread(func: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
    """在线程池中运行 ``func(*args, **kwargs)`` 并等待结果。"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(get_executor(), partial(func, *args, **kwargs))


async def to_thread(func: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
    """可用时等价于 ``asyncio.to_thread``，否则退回 ``run_in_thread``。"""
    if hasattr(asyncio, "to_thread"):
        return await asyncio.to_thread(func, *args, **kwargs)
    return await run_in_thread(func, *args, **kwargs)
