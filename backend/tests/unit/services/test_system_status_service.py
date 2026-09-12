"""服务状态探测服务单测：并发探测、异常/超时降级。"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.system_status import SystemStatusResponse
from app.services.admin import system_status_service as svc_module
from app.services.admin.system_status_service import SystemStatusService


def _service() -> SystemStatusService:
    return SystemStatusService(AsyncMock(spec=AsyncSession))


def _patch_checks(
    *,
    postgres: str = "PostgreSQL 16.4",
    redis: str = "PONG",
    elasticsearch: str = "v8.13.0",
    minio: str = "bucket invest-files 可访问",
) -> dict[str, AsyncMock]:
    mocks = {
        "_check_postgres": AsyncMock(return_value=postgres),
        "_check_redis": AsyncMock(return_value=redis),
        "_check_elasticsearch": AsyncMock(return_value=elasticsearch),
        "_check_minio": AsyncMock(return_value=minio),
    }
    return {
        name: patch.object(SystemStatusService, name, mock)
        for name, mock in mocks.items()
    }


def _item_of(result: SystemStatusResponse, key: str):
    return next(i for i in result.items if i.key == key)


@pytest.mark.unit
class TestGetStatus:
    async def test_all_up_operational(self) -> None:
        patches = _patch_checks()
        with patches["_check_postgres"], patches["_check_redis"], patches[
            "_check_elasticsearch"
        ], patches["_check_minio"]:
            result = await _service().get_status()

        assert result.overall == "operational"
        assert [i.key for i in result.items] == [
            "postgres",
            "redis",
            "elasticsearch",
            "minio",
        ]
        redis = _item_of(result, "redis")
        assert redis.status == "up"
        assert redis.detail == "PONG"
        assert redis.error is None
        assert redis.latency_ms is not None
        assert result.checked_at.tzinfo is not None

    async def test_single_failure_degrades_overall(self) -> None:
        """任一服务 down 只降级该项，其余照常返回（端点不 500）。"""
        patches = _patch_checks()
        redis_mock = AsyncMock(side_effect=RedisError("connection refused"))
        with patches["_check_postgres"], patch.object(
            SystemStatusService, "_check_redis", redis_mock
        ), patches["_check_elasticsearch"], patches["_check_minio"]:
            result = await _service().get_status()

        assert result.overall == "degraded"
        redis = _item_of(result, "redis")
        assert redis.status == "down"
        assert redis.latency_ms is None
        assert "connection refused" in redis.error
        assert _item_of(result, "postgres").status == "up"
        assert _item_of(result, "minio").status == "up"

    async def test_probe_timeout_degrades(self) -> None:
        """慢依赖被 wait_for 截断为 down，不拖挂端点。"""
        patches = _patch_checks()

        async def slow_check() -> str:
            await asyncio.sleep(1)
            return "PONG"

        settings = AsyncMock()
        settings.status_probe_timeout = 0.01
        with (
            patches["_check_postgres"],
            patch.object(SystemStatusService, "_check_redis", AsyncMock(side_effect=slow_check)),
            patches["_check_elasticsearch"],
            patches["_check_minio"],
            patch.object(svc_module, "get_settings", return_value=settings),
        ):
            result = await _service().get_status()

        redis = _item_of(result, "redis")
        assert redis.status == "down"
        assert "超时" in redis.error

    async def test_all_down_still_returns_response(self) -> None:
        """全部依赖故障时仍返回完整结构（degraded），供后台页面渲染。"""
        failing = AsyncMock(side_effect=RuntimeError("boom"))
        with (
            patch.object(SystemStatusService, "_check_postgres", failing),
            patch.object(SystemStatusService, "_check_redis", failing),
            patch.object(SystemStatusService, "_check_elasticsearch", failing),
            patch.object(SystemStatusService, "_check_minio", failing),
        ):
            result = await _service().get_status()

        assert result.overall == "degraded"
        assert all(i.status == "down" for i in result.items)
