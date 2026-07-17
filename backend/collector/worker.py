"""Collector worker that consumes tasks from Redis and executes them.

The worker is the long-running process inside the collector Docker container. It
polls the Redis queue populated by the web API, updates ``CollectorLog`` rows,
and runs tasks through ``collector.scf_handler._run_task`` so that local Docker
and Tencent SCF share the same execution path.
"""

import asyncio
import logging
import signal
import traceback
from datetime import datetime, timezone
from typing import Any

from app.core.database import AsyncSessionLocal
from app.models.collector_log import CollectorLog
from collector.base import CollectResult
from collector.queue import CollectorQueue
from collector.scf_handler import _run_task
from collector.scheduler import start_scheduler

logger = logging.getLogger(__name__)

DEFAULT_POP_TIMEOUT = 5


class WorkerState:
    """Mutable worker state shared with signal handlers."""

    def __init__(self) -> None:
        self.running = True


async def _update_log_running(log_id: int) -> None:
    async with AsyncSessionLocal() as session:
        log = await session.get(CollectorLog, log_id)
        if log is not None:
            log.status = "running"
            log.started_at = datetime.now(timezone.utc)
            await session.commit()


async def _update_log_result(log_id: int, result: CollectResult) -> None:
    async with AsyncSessionLocal() as session:
        log = await session.get(CollectorLog, log_id)
        if log is not None:
            log.status = result.status.value
            log.source = result.source
            log.finished_at = result.finished_at or datetime.now(timezone.utc)
            log.records_count = result.items_stored
            log.error_msg = "\n".join(result.errors) if result.errors else None
            log.meta = {**(log.meta or {}), **(result.metadata or {})}
            await session.commit()


async def _update_log_error(log_id: int, exc: Exception) -> None:
    async with AsyncSessionLocal() as session:
        log = await session.get(CollectorLog, log_id)
        if log is not None:
            log.status = "failed"
            log.finished_at = datetime.now(timezone.utc)
            log.error_msg = f"{exc!r}\n{traceback.format_exc()}"
            await session.commit()


async def _execute_payload(payload: dict[str, Any]) -> None:
    """Execute a single task payload and update its log entry."""
    log_id = payload.get("log_id")
    task_name = payload.get("task", "unknown")

    if log_id is not None:
        await _update_log_running(log_id)

    try:
        result = await _run_task(payload)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Collector task %s failed", task_name)
        if log_id is not None:
            await _update_log_error(log_id, exc)
        return

    if log_id is not None:
        await _update_log_result(log_id, result)

    logger.info(
        "collector_task_finished: task=%s source=%s status=%s "
        "collected=%d stored=%d errors=%d",
        task_name,
        result.source,
        result.status.value,
        result.items_collected,
        result.items_stored,
        len(result.errors),
    )


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

            await _execute_payload(payload)
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
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
