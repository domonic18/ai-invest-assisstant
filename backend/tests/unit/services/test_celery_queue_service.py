"""Celery 队列状态服务单测：broker 信封解码 / 三来源归组 / broker 降级。"""

import base64
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.exceptions import RedisError

from app.models.collector_log import CollectorLog
from app.services.admin import celery_queue_service as svc_module
from app.services.admin.celery_queue_service import (
    CeleryQueueService,
    decode_broker_message,
)

_NOW = datetime(2026, 9, 24, 8, 0, tzinfo=timezone.utc)


def _envelope(task: str, *, source: str | None = "sina", celery_id: str = "cid-1") -> str:
    """构造真实形状的 Kombu JSON 信封。"""
    body = base64.b64encode(
        json.dumps(
            {"args": [{"task": task, "preferred_source": source}], "kwargs": {}, "embed": []}
        ).encode()
    ).decode()
    return json.dumps({"body": body, "headers": {"id": celery_id}})


def _log_row(**overrides: object) -> CollectorLog:
    payload: dict[str, object] = {
        "id": 1,
        "task_name": "stock-minute",
        "source": "sina",
        "status": "success",
        "celery_task_id": "cel-1",
        "started_at": _NOW - timedelta(minutes=5),
        "finished_at": _NOW - timedelta(seconds=259, milliseconds=100),
        "records_count": 10,
        "error_msg": None,
        "message": "ok",
        "meta": {},
    }
    payload.update(overrides)
    return CollectorLog(**payload)


@pytest.mark.unit
class TestDecodeBrokerMessage:
    def test_decodes_kombu_envelope(self) -> None:
        msg = decode_broker_message(_envelope("kb-extract", celery_id="abc-def"))
        assert msg == {
            "task_type": "kb-extract",
            "source": "sina",
            "celery_id": "abc-def",
        }

    def test_malformed_items_return_none(self) -> None:
        assert decode_broker_message("not-json") is None
        assert decode_broker_message(json.dumps({"headers": {}})) is None
        body = base64.b64encode(json.dumps({"args": ["not-a-dict"]}).encode()).decode()
        assert decode_broker_message(json.dumps({"body": body})) is None

    def test_missing_task_type_falls_back_to_none_field(self) -> None:
        body = base64.b64encode(json.dumps({"args": [{}]}).encode()).decode()
        msg = decode_broker_message(json.dumps({"body": body, "headers": {}}))
        assert msg is not None
        assert msg["task_type"] is None


@pytest.mark.unit
class TestCeleryQueueService:
    def _service(self, session: AsyncMock | None = None) -> CeleryQueueService:
        return CeleryQueueService(session or AsyncMock())

    async def test_overview_groups_by_queue_in_order(self) -> None:
        running = _log_row(
            id=10, task_name="stock-minute", status="running", finished_at=None
        )
        terminal_success = _log_row(id=11, status="success")
        terminal_failed = _log_row(
            id=12,
            status="failed",
            error_msg="x" * 300,
            finished_at=_NOW - timedelta(seconds=30),
        )
        pending = [
            {"task_type": "stock-minute", "source": "sina", "celery_id": "p1"},
            {"task_type": "kb-transcribe", "source": None, "celery_id": "p2"},
        ]
        with (
            patch.object(
                CeleryQueueService,
                "_fetch_broker_pending",
                AsyncMock(
                    return_value=(
                        True,
                        {
                            "collector.realtime": (3, [pending[0]]),
                            "collector.batch": (0, []),
                            "collector.heavy": (1, [pending[1]]),
                        },
                    )
                ),
            ),
            patch.object(
                CeleryQueueService,
                "_fetch_log_rows",
                AsyncMock(return_value=([running], [terminal_failed, terminal_success])),
            ),
            patch(
                "app.services.admin.celery_queue_service.resolve_queue",
                lambda task, source=None: "collector.realtime"
                if task == "stock-minute"
                else "collector.heavy",
            ),
        ):
            overview = await self._service().get_overview()

        assert overview["broker_ok"] is True
        queues = {q["name"]: q for q in overview["queues"]}
        realtime = queues["collector.realtime"]
        assert realtime["pending_total"] == 3
        states = [t["state"] for t in realtime["tasks"]]
        # running → pending → 终态（新→旧）
        assert states == ["running", "pending", "failed", "success"]
        assert realtime["tasks"][0]["key"] == "log-10"
        assert realtime["tasks"][1]["key"] == "pending-0-p1"
        assert len(realtime["tasks"][2]["detail"] or "") == 200
        heavy = queues["collector.heavy"]
        assert [t["state"] for t in heavy["tasks"]] == ["pending"]
        assert heavy["tasks"][0]["label"] != ""

    async def test_duration_and_row_square_fields(self) -> None:
        row = _log_row()
        square = self._service()._row_square(row)
        assert square["duration_ms"] == 40900
        assert square["label"]  # TASK_SPECS 中存在 stock-minute 的中文标签
        assert square["state"] == "success"

    async def test_broker_down_degrades_to_db_only(self) -> None:
        redis_client = MagicMock()
        redis_client.llen = AsyncMock(side_effect=RedisError("conn refused"))
        redis_client.aclose = AsyncMock()
        with patch.object(svc_module, "from_url", MagicMock(return_value=redis_client)):
            broker_ok, pending = await self._service()._fetch_broker_pending()
        assert broker_ok is False
        assert pending == {}
        redis_client.aclose.assert_awaited_once()
