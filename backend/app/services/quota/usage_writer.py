"""计量明细落库：后台任务直写，永不阻断主请求。

不使用进程级队列+flusher：Celery worker 每任务经 ``asyncio.run`` 起新事件循环，
队列与常驻 flush 任务无法跨循环存活；本域写入量级为每次 LLM 调用一条（日千级），
逐条短会话后台写完全够用且在任意执行环境（web/celery/CLI）行为一致。
写失败降级记 structlog 事件（字段完整，供人工补偿）。
"""

import asyncio
from dataclasses import dataclass

import structlog

from app.core.database import AsyncSessionLocal
from app.models.account_quota import UserTokenUsage

logger = structlog.get_logger(__name__)

_tasks: set[asyncio.Task[None]] = set()


@dataclass(frozen=True)
class UsageRecord:
    """单次模型调用的计量明细。"""

    user_id: int | None
    feature: str
    model_name: str
    provider: str
    outlet: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated: bool


def enqueue(record: UsageRecord) -> None:
    """投递一条计量记录（fire-and-forget 后台写；无运行中循环时记日志丢弃）。"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("usage_write_dropped_no_loop", **_fields(record))
        return
    task = loop.create_task(_write(record))
    # asyncio 仅弱引用运行中任务，必须显式持引用防 GC 中断写入
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def _write(record: UsageRecord) -> None:
    try:
        async with AsyncSessionLocal() as session:
            session.add(
                UserTokenUsage(
                    user_id=record.user_id,
                    feature=record.feature,
                    model_name=record.model_name,
                    provider=record.provider,
                    outlet=record.outlet,
                    prompt_tokens=record.prompt_tokens,
                    completion_tokens=record.completion_tokens,
                    total_tokens=record.total_tokens,
                    estimated=record.estimated,
                )
            )
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("usage_write_dropped", **_fields(record), error=str(exc))


def _fields(record: UsageRecord) -> dict[str, object]:
    return {
        "user_id": record.user_id,
        "feature": record.feature,
        "model_name": record.model_name,
        "provider": record.provider,
        "outlet": record.outlet,
        "prompt_tokens": record.prompt_tokens,
        "completion_tokens": record.completion_tokens,
        "total_tokens": record.total_tokens,
        "estimated": record.estimated,
    }
