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

import structlog

_executor: ThreadPoolExecutor | None = None

logger = structlog.get_logger(__name__)

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


async def run_in_thread(
    func: Callable[..., Any],
    /,
    *args: Any,
    timeout: float | None = None,
    **kwargs: Any,
) -> Any:
    """在线程池中运行 ``func(*args, **kwargs)`` 并等待结果。

    Args:
        func: 同步函数。
        timeout: 可选等待上限（秒）。超时抛 ``TimeoutError``——线程本身无法
            被终止，会继续运行到自然结束（配合 worker 进程的 requests 默认
            超时兜底，最长再挂一个超时周期）；本参数的价值是让任务逻辑立即
            失败、走渠道 fallback，而非逐请求等待。
    """
    loop = asyncio.get_running_loop()
    future = loop.run_in_executor(get_executor(), partial(func, *args, **kwargs))
    if timeout is None:
        return await future
    try:
        return await asyncio.wait_for(future, timeout)
    except TimeoutError:
        logger.warning(
            "run_in_thread_timeout",
            func=getattr(func, "__name__", repr(func)),
            timeout=timeout,
        )
        raise


async def to_thread(func: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
    """可用时等价于 ``asyncio.to_thread``，否则退回 ``run_in_thread``。"""
    if hasattr(asyncio, "to_thread"):
        return await asyncio.to_thread(func, *args, **kwargs)
    return await run_in_thread(func, *args, **kwargs)
