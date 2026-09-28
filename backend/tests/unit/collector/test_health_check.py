"""health_check 内部采集器契约测试：metadata 只收 JSON 可序列化标量。"""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from collector.core.base import CollectStatus
from collector.spiders.health_check import HealthCheckCollector


def _summary(checked_at: datetime) -> dict[str, Any]:
    return {
        "checked_at": checked_at,
        "total": 66,
        "failed": 0,
        "orphaned": 0,
        "status_counts": {"healthy": 60, "degraded": 6},
    }


@pytest.mark.unit
class TestHealthCheckCollector:
    @pytest.mark.asyncio
    async def test_metadata_checked_at_serialized_to_iso(self) -> None:
        """checked_at 原生 datetime 进 JSONB metadata 会炸 TypeError
        （2026-09-26~09-28 health-check 连败三日的根因），必须 isoformat。"""
        checked = datetime(2026, 9, 28, 0, 30, 0, tzinfo=timezone.utc)
        mock_session = AsyncMock()
        factory = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_session),
                __aexit__=AsyncMock(return_value=None),
            )
        )
        with (
            patch(
                "app.services.collector.health.health_service.run_check",
                AsyncMock(return_value=_summary(checked)),
            ),
            patch("app.core.database.AsyncSessionLocal", factory),
        ):
            result = await HealthCheckCollector(
                {"source": "internal", "data_type": "health-check"}
            ).run()

        assert result.status == CollectStatus.SUCCESS
        assert result.errors == []
        assert result.metadata is not None
        assert result.metadata["checked_at"] == "2026-09-28T00:30:00+00:00"
        assert result.metadata["instances"] == 66
        assert result.metadata["status_counts"] == {"healthy": 60, "degraded": 6}

    @pytest.mark.asyncio
    async def test_partial_when_judge_failures(self) -> None:
        summary = _summary(datetime.now(timezone.utc)) | {"failed": 2}
        mock_session = AsyncMock()
        factory = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_session),
                __aexit__=AsyncMock(return_value=None),
            )
        )
        with (
            patch(
                "app.services.collector.health.health_service.run_check",
                AsyncMock(return_value=summary),
            ),
            patch("app.core.database.AsyncSessionLocal", factory),
        ):
            result = await HealthCheckCollector(
                {"source": "internal", "data_type": "health-check"}
            ).run()

        assert result.status == CollectStatus.PARTIAL
        assert result.errors and "2 个实例" in result.errors[0]
