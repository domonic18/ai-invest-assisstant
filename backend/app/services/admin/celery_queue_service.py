"""Celery 队列任务状态总览服务（SystemStatus 页方框网格数据源）。

状态三来源：
- pending：Redis broker 队列里的 Kombu JSON 信封（base64 body 解出任务名）
- running：collector_log.status='running' 行（worker 挂死时停留此态，即假活证据）
- 终态：collector_log 最近窗口内 success/partial/failed/skipped 行

队列归属：collector_log 无 queue 列，按 task_name（TASK_SPECS 键）用
resolve_queue 现算；broker 不可达时降级仅返回 DB 侧数据（broker_ok=false），
与 cache 层容错同一原则——观测接口不允许因基础设施故障打挂。
"""

import base64
import json
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from redis.asyncio import from_url
from redis.exceptions import RedisError
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.collector_log import CollectorLog
from collector.celery_app import resolve_queue
from collector.runtime.registry import TASK_SPECS

logger = structlog.get_logger(__name__)

PENDING_SAMPLE_LIMIT = 50
TERMINAL_WINDOW = timedelta(minutes=30)
TERMINAL_LIMIT = 60
RUNNING_LIMIT = 20
BROKER_SOCKET_TIMEOUT = 2.0
DETAIL_MAX_CHARS = 200

QUEUE_LABELS: dict[str, str] = {
    "collector.realtime": "实时队列",
    "collector.batch": "批量队列",
    "collector.heavy": "重载队列",
}


def task_label(task_type: str | None) -> str:
    """TASK_SPECS 键 → 中文任务标签；未知键原样返回。"""
    if not task_type:
        return "未知任务"
    spec = TASK_SPECS.get(task_type)
    return spec.label if spec is not None else task_type


def decode_broker_message(raw: bytes | str) -> dict[str, Any] | None:
    """Kombu JSON 信封 → {'task_type', 'source', 'celery_id'}；畸形消息返回 None。

    信封形状：``{"body": <base64>, "headers": {"id": ...}}``，body 解码后为
    ``{"args": [{"task": <task_type>, "preferred_source": ..., ...}], ...}``。
    """
    try:
        envelope = json.loads(raw)
        body = envelope.get("body")
        if not body:
            return None
        payload = json.loads(base64.b64decode(body))
        args = payload.get("args") or []
        inner = args[0] if args else None
        if not isinstance(inner, dict):
            return None
        headers = envelope.get("headers") or {}
        return {
            "task_type": inner.get("task"),
            "source": inner.get("preferred_source"),
            "celery_id": headers.get("id"),
        }
    except (ValueError, TypeError, AttributeError) as exc:
        logger.debug("broker_message_decode_failed", error=str(exc))
        return None


class CeleryQueueService:
    """聚合 broker 待执行消息与 collector_log 运行/终态。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_overview(self) -> dict[str, Any]:
        """返回三队列任务方框总览（wire 前的 snake_case dict）。"""
        broker_ok, pending = await self._fetch_broker_pending()
        running_rows, terminal_rows = await self._fetch_log_rows()
        queues = [
            self._build_queue(name, pending.get(name), running_rows, terminal_rows)
            for name in QUEUE_LABELS
        ]
        return {
            "broker_ok": broker_ok,
            "queues": queues,
            "checked_at": datetime.now(timezone.utc),
        }

    async def _fetch_broker_pending(
        self,
    ) -> tuple[bool, dict[str, tuple[int, list[dict[str, Any]]]]]:
        """采样各队列待执行消息；返回 (broker 可达, {队列: (总长, 解码样本)})。"""
        settings = get_settings()
        client = from_url(
            str(settings.celery_broker_url),
            socket_connect_timeout=BROKER_SOCKET_TIMEOUT,
            socket_timeout=BROKER_SOCKET_TIMEOUT,
        )
        try:
            result: dict[str, tuple[int, list[dict[str, Any]]]] = {}
            for name in QUEUE_LABELS:
                total = int(await client.llen(name) or 0)
                raw_items = await client.lrange(name, 0, PENDING_SAMPLE_LIMIT - 1)
                decoded = [
                    msg
                    for msg in (decode_broker_message(raw) for raw in raw_items)
                    if msg is not None
                ]
                result[name] = (total, decoded)
            return True, result
        except RedisError as exc:
            logger.warning("celery_broker_unreachable", error=str(exc))
            return False, {}
        finally:
            await client.aclose()

    async def _fetch_log_rows(
        self,
    ) -> tuple[list[CollectorLog], list[CollectorLog]]:
        """running 行（全部，cap 后）+ 最近窗口终态行，各按时间倒序。"""
        since = datetime.now(timezone.utc) - TERMINAL_WINDOW
        running = (
            (
                await self._session.execute(
                    select(CollectorLog)
                    .where(CollectorLog.status == "running")
                    .order_by(desc(CollectorLog.started_at))
                    .limit(RUNNING_LIMIT)
                )
            )
            .scalars()
            .all()
        )
        terminal = (
            (
                await self._session.execute(
                    select(CollectorLog)
                    .where(
                        CollectorLog.status.notin_(["running", "pending"]),
                        CollectorLog.finished_at >= since,
                    )
                    .order_by(desc(CollectorLog.finished_at))
                    .limit(TERMINAL_LIMIT)
                )
            )
            .scalars()
            .all()
        )
        return list(running), list(terminal)

    def _build_queue(
        self,
        name: str,
        pending_info: tuple[int, list[dict[str, Any]]] | None,
        running_rows: list[CollectorLog],
        terminal_rows: list[CollectorLog],
    ) -> dict[str, Any]:
        """单队列装配：running（转圈）→ pending（灰）→ 终态（绿/红，新→旧）。"""
        pending_total, pending_msgs = pending_info if pending_info else (0, [])
        squares = [
            self._row_square(row, state="running")
            for row in running_rows
            if resolve_queue(row.task_name) == name
        ]
        squares.extend(
            self._pending_square(index, msg) for index, msg in enumerate(pending_msgs)
        )
        squares.extend(
            self._row_square(row) for row in terminal_rows if resolve_queue(row.task_name) == name
        )
        return {
            "name": name,
            "label": QUEUE_LABELS[name],
            "pending_total": pending_total,
            "tasks": squares,
        }

    def _row_square(
        self, row: CollectorLog, *, state: str | None = None
    ) -> dict[str, Any]:
        """collector_log 行 → 方框 dict。"""
        resolved = state or row.status
        duration_ms: int | None = None
        if row.started_at is not None and row.finished_at is not None:
            duration_ms = int((row.finished_at - row.started_at).total_seconds() * 1000)
        detail: str | None = None
        if resolved == "failed" and row.error_msg:
            detail = row.error_msg[:DETAIL_MAX_CHARS]
        elif row.message:
            detail = row.message[:DETAIL_MAX_CHARS]
        return {
            "key": f"log-{row.id}",
            "task_type": row.task_name,
            "label": task_label(row.task_name),
            "state": resolved,
            "source": row.source,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
            "duration_ms": duration_ms,
            "detail": detail,
        }

    def _pending_square(self, index: int, msg: dict[str, Any]) -> dict[str, Any]:
        """broker 待执行消息 → 方框 dict（排队中无时间信息）。"""
        task_type = msg.get("task_type") or "unknown"
        celery_id = str(msg.get("celery_id") or index)[:8]
        return {
            "key": f"pending-{index}-{celery_id}",
            "task_type": task_type,
            "label": task_label(task_type),
            "state": "pending",
            "source": msg.get("source"),
            "started_at": None,
            "finished_at": None,
            "duration_ms": None,
            "detail": None,
        }
