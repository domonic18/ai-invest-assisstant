"""服务状态探测服务单测：并发探测、类别分组、异常/超时降级。"""

import asyncio
import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.system_status import SystemStatusResponse
from app.services.admin import system_status_service as svc_module
from app.services.admin.system_status_service import SystemStatusService

WORKERS_UP_DETAIL = "2/2 节点应答：heavy@abc, realtime@xyz"
LLM_UP_DETAIL = "3 个启用配置（chat×2 · embedding×1）· 仅展示配置就绪，未探测连通性"


def _settings(
    *,
    paper_trade_url: str = "",
    douyin_signer_url: str = "",
    status_probe_timeout: float = 3.0,
) -> SimpleNamespace:
    return SimpleNamespace(
        status_probe_timeout=status_probe_timeout,
        paper_trade_url=paper_trade_url,
        douyin_signer_url=douyin_signer_url,
        celery_broker_url="redis://localhost:6379/1",
    )


def _patch_checks(**overrides: AsyncMock) -> dict[str, AsyncMock]:
    defaults: dict[str, AsyncMock] = {
        "_check_postgres": AsyncMock(return_value="PostgreSQL 16.4"),
        "_check_redis": AsyncMock(return_value="PONG"),
        "_check_minio": AsyncMock(return_value="bucket invest-files 可访问"),
        "_check_celery_broker": AsyncMock(return_value="PONG"),
        "_check_celery_workers": AsyncMock(return_value=WORKERS_UP_DETAIL),
        "_check_llm_configs": AsyncMock(return_value=LLM_UP_DETAIL),
        "_check_paper_trade": AsyncMock(return_value="适配器在线"),
        "_check_douyin_signer": AsyncMock(return_value="在线（热身槽位 1）"),
    }
    defaults.update(overrides)
    return {
        name: patch.object(SystemStatusService, name, mock)
        for name, mock in defaults.items()
    }


async def _get_status(
    *,
    settings: SimpleNamespace | None = None,
    **check_overrides: AsyncMock,
) -> SystemStatusResponse:
    service = SystemStatusService(AsyncMock(spec=AsyncSession))
    settings_patch = patch.object(
        svc_module, "get_settings", return_value=settings or _settings()
    )
    with contextlib.ExitStack() as stack:
        for p in _patch_checks(**check_overrides).values():
            stack.enter_context(p)
        stack.enter_context(settings_patch)
        return await service.get_status()
    raise AssertionError("unreachable")  # pragma: no cover


def _item_of(result: SystemStatusResponse, key: str):
    return next(i for i in result.items if i.key == key)


@pytest.mark.unit
class TestGetStatus:
    async def test_all_up_operational(self) -> None:
        result = await _get_status()

        assert result.overall == "operational"
        assert [i.key for i in result.items] == [
            "postgres",
            "redis",
            "minio",
            "celery-broker",
            "celery-workers",
            "llm-configs",
        ]
        assert [i.category for i in result.items] == [
            "storage",
            "storage",
            "storage",
            "compute",
            "compute",
            "external",
        ]
        workers = _item_of(result, "celery-workers")
        assert workers.status == "up"
        assert workers.detail == WORKERS_UP_DETAIL
        assert workers.latency_ms is not None
        assert result.checked_at.tzinfo is not None

    async def test_optional_services_included_when_configured(self) -> None:
        settings = _settings(
            paper_trade_url="http://paper-trade:8000",
            douyin_signer_url="http://douyin-signer:3000",
        )
        result = await _get_status(settings=settings)

        assert [i.key for i in result.items] == [
            "postgres",
            "redis",
            "minio",
            "celery-broker",
            "celery-workers",
            "paper-trade",
            "douyin-signer",
            "llm-configs",
        ]
        assert all(i.category == "compute" for i in result.items[3:6])

    async def test_single_failure_degrades_overall(self) -> None:
        """任一核心服务 down 只降级该项，其余照常返回（端点不 500）。"""
        result = await _get_status(
            _check_celery_workers=AsyncMock(side_effect=RuntimeError("heavy 队列节点离线"))
        )

        assert result.overall == "degraded"
        workers = _item_of(result, "celery-workers")
        assert workers.status == "down"
        assert workers.latency_ms is None
        assert "heavy" in workers.error
        assert _item_of(result, "postgres").status == "up"
        assert _item_of(result, "llm-configs").status == "up"

    async def test_external_down_does_not_degrade_overall(self) -> None:
        """external 类（LLM 清单）不参与 overall 判定。"""
        result = await _get_status(
            _check_llm_configs=AsyncMock(side_effect=RuntimeError("无已启用的 LLM 配置"))
        )

        assert result.overall == "operational"
        llm = _item_of(result, "llm-configs")
        assert llm.status == "down"
        assert "无已启用" in llm.error

    async def test_probe_timeout_degrades(self) -> None:
        """慢依赖被 wait_for 截断为 down，不拖挂端点。"""

        async def slow_check() -> str:
            await asyncio.sleep(1)
            return "PONG"

        result = await _get_status(
            settings=_settings(status_probe_timeout=0.01),
            _check_redis=AsyncMock(side_effect=slow_check),
        )

        redis = _item_of(result, "redis")
        assert redis.status == "down"
        assert "超时" in redis.error


@pytest.mark.unit
class TestCeleryWorkersCheck:
    def _celery_mock(self, replies: dict[str, object]) -> MagicMock:
        celery = MagicMock()
        celery.control.inspect.return_value.ping.return_value = replies
        return celery

    async def test_both_nodes_up(self) -> None:
        celery = self._celery_mock({"realtime@xyz": ["pong"], "heavy@abc": ["pong"]})
        with patch("collector.celery_app.app", celery):
            detail = await SystemStatusService(AsyncMock(spec=AsyncSession))._check_celery_workers()

        assert detail == "2/2 节点应答：heavy@abc, realtime@xyz"

    async def test_missing_heavy_node_fails(self) -> None:
        celery = self._celery_mock({"realtime@xyz": ["pong"]})
        with patch("collector.celery_app.app", celery):
            with pytest.raises(RuntimeError, match="heavy"):
                await SystemStatusService(AsyncMock(spec=AsyncSession))._check_celery_workers()

    async def test_no_reply_fails(self) -> None:
        celery = self._celery_mock({})
        with patch("collector.celery_app.app", celery):
            with pytest.raises(RuntimeError, match="无节点应答"):
                await SystemStatusService(AsyncMock(spec=AsyncSession))._check_celery_workers()


@pytest.mark.unit
class TestLlmConfigsCheck:
    async def test_breakdown_by_purpose(self) -> None:
        session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.all.return_value = [("chat", 2), ("embedding", 1)]
        session.execute.return_value = result

        detail = await SystemStatusService(session)._check_llm_configs()

        assert "3 个启用配置" in detail
        assert "chat×2" in detail
        assert "embedding×1" in detail
        assert "未探测连通性" in detail

    async def test_empty_configs_raises(self) -> None:
        session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.all.return_value = []
        session.execute.return_value = result

        with pytest.raises(RuntimeError, match="无已启用"):
            await SystemStatusService(session)._check_llm_configs()


@pytest.mark.unit
class TestCeleryBrokerCheck:
    async def test_ping_ok(self) -> None:
        client = AsyncMock()
        client.ping.return_value = True
        client.aclose.return_value = None
        with patch.object(svc_module.aioredis, "from_url", return_value=client):
            detail = await SystemStatusService(AsyncMock(spec=AsyncSession))._check_celery_broker()

        assert detail == "PONG"
        client.aclose.assert_awaited_once()

    async def test_redis_error_raises_runtime_error(self) -> None:
        client = AsyncMock()
        client.ping.side_effect = RedisError("connection refused")
        client.aclose.return_value = None
        with patch.object(svc_module.aioredis, "from_url", return_value=client):
            with pytest.raises(RuntimeError, match="broker 不可达"):
                await SystemStatusService(AsyncMock(spec=AsyncSession))._check_celery_broker()
