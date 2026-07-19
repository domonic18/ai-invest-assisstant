"""Collector worker that consumes tasks from Redis and executes them.

The worker is the long-running process inside the collector Docker container. It
polls the Redis queue populated by the web API and runs tasks through
``collector.runtime.runner.run_task`` — the same execution path used by the
scheduler, CLI, and Tencent SCF (collector_log 回写也在 runner 内完成）。
"""

import asyncio
import logging
import signal
from typing import Any

from collector.runtime.queue import CollectorQueue
from collector.runtime.runner import run_task
from collector.runtime.scheduler import start_scheduler

logger = logging.getLogger(__name__)

DEFAULT_POP_TIMEOUT = 5


class WorkerState:
    """Mutable worker state shared with signal handlers."""

    def __init__(self) -> None:
        self.running = True


async def _worker_loop(state: WorkerState, pop_timeout: int) -> None:
    queue = CollectorQueue()
    logger.info("Collector worker started, polling queue: %s", queue.queue_key)

    try:
        while state.running:
            try:
                payload = await queue.pop(timeout=pop_timeout)
            except Exception:  # noqa: BLE001
                logger.exception("Failed to pop from queue, retrying")
                await asyncio.sleep(1)
                continue

            if payload is None:
                continue

            try:
                await run_task(payload)
            except Exception:  # noqa: BLE001
                # run_task 已记录异常并回写 collector_log，此处仅保证循环存活
                pass
    finally:
        await queue.close()
        logger.info("Collector worker stopped")


async def run_worker(pop_timeout: int = DEFAULT_POP_TIMEOUT) -> None:
    """Run the collector worker loop and scheduler until SIGTERM is received."""
    state = WorkerState()

    def _handle_signal(signum: int, frame: Any) -> None:
        logger.info("Received signal %s, shutting down worker", signum)
        state.running = False

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    scheduler = await start_scheduler()
    try:
        await _worker_loop(state, pop_timeout)
    finally:
        scheduler.shutdown(wait=False)


def main() -> None:
    """CLI entry point for the collector worker."""
    from collector.core.logging import configure_logging

    configure_logging()
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
