"""知识库嵌入物化采集器测试（internal 薄壳委托 index_service）。"""

from unittest.mock import AsyncMock, patch

import pytest

from collector.core.base import CollectStatus
from collector.spiders.kb_index import KbIndexCollector


def _collector() -> KbIndexCollector:
    return KbIndexCollector({"source": "internal", "data_type": "kb_index"})


@pytest.mark.unit
class TestKbIndexRun:
    async def test_materialized_reports_success(self) -> None:
        stats = {
            "phase": "incremental",
            "pointsEmbedded": 1,
            "segmentsEmbedded": 2,
            "imagesEmbedded": 3,
            "pointsCleared": 1,
            "segmentsCleared": 0,
            "imagesCleared": 2,
        }
        with (
            patch("collector.spiders.kb_index.AsyncSessionLocal") as mock_factory,
            patch(
                "collector.spiders.kb_index.index_service.run_index",
                new=AsyncMock(return_value=stats),
            ) as p_run,
        ):
            mock_factory.return_value.__aenter__.return_value = AsyncMock()
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        assert result.items_stored == 9
        assert result.metadata == stats
        assert p_run.call_args.kwargs["force_rebuild"] is False

    async def test_skipped_busy_is_benign(self) -> None:
        stats = {"skippedBusy": 1}
        with (
            patch("collector.spiders.kb_index.AsyncSessionLocal") as mock_factory,
            patch(
                "collector.spiders.kb_index.index_service.run_index",
                new=AsyncMock(return_value=stats),
            ),
        ):
            mock_factory.return_value.__aenter__.return_value = AsyncMock()
            result = await _collector().run()

        assert result.status == CollectStatus.SKIPPED
        assert "锁占用" in (result.message or "")

    async def test_no_model_configured_is_benign(self) -> None:
        stats = {"noModelConfigured": 1}
        with (
            patch("collector.spiders.kb_index.AsyncSessionLocal") as mock_factory,
            patch(
                "collector.spiders.kb_index.index_service.run_index",
                new=AsyncMock(return_value=stats),
            ),
        ):
            mock_factory.return_value.__aenter__.return_value = AsyncMock()
            result = await _collector().run()

        assert result.status == CollectStatus.SKIPPED
        assert "embedding 模型未配置" in (result.message or "")

    async def test_dimension_mismatch_skips_with_migration_hint(self) -> None:
        stats = {"dimensionMismatch": 1, "expectedDims": 2048, "actualDims": 1024}
        with (
            patch("collector.spiders.kb_index.AsyncSessionLocal") as mock_factory,
            patch(
                "collector.spiders.kb_index.index_service.run_index",
                new=AsyncMock(return_value=stats),
            ),
        ):
            mock_factory.return_value.__aenter__.return_value = AsyncMock()
            result = await _collector().run()

        assert result.status == CollectStatus.SKIPPED
        assert "1024" in (result.message or "")
        assert "force_rebuild" in (result.message or "")

    async def test_nothing_dirty_is_benign_skipped(self) -> None:
        stats = {
            "phase": "incremental",
            "dirtyPoints": 0,
            "dirtySegments": 0,
            "dirtyImages": 0,
        }
        with (
            patch("collector.spiders.kb_index.AsyncSessionLocal") as mock_factory,
            patch(
                "collector.spiders.kb_index.index_service.run_index",
                new=AsyncMock(return_value=stats),
            ),
        ):
            mock_factory.return_value.__aenter__.return_value = AsyncMock()
            result = await _collector().run()

        assert result.status == CollectStatus.SKIPPED
        assert "没有待物化变更" in (result.message or "")

    async def test_force_rebuild_param_forwarded(self) -> None:
        stats = {"phase": "rebuild", "forceRebuild": 1, "pointsEmbedded": 1}
        with (
            patch("collector.spiders.kb_index.AsyncSessionLocal") as mock_factory,
            patch(
                "collector.spiders.kb_index.index_service.run_index",
                new=AsyncMock(return_value=stats),
            ) as p_run,
        ):
            mock_factory.return_value.__aenter__.return_value = AsyncMock()
            result = await _collector().run(force_rebuild="true")

        assert result.status == CollectStatus.SUCCESS
        assert p_run.call_args.kwargs["force_rebuild"] is True

    async def test_partial_kinds_report_partial(self) -> None:
        stats = {
            "phase": "incremental",
            "pointsEmbedded": 1,
            "segmentsEmbedded": 0,
            "imagesEmbedded": 0,
            "failedKinds": ["segment", "image"],
        }
        with (
            patch("collector.spiders.kb_index.AsyncSessionLocal") as mock_factory,
            patch(
                "collector.spiders.kb_index.index_service.run_index",
                new=AsyncMock(return_value=stats),
            ),
        ):
            mock_factory.return_value.__aenter__.return_value = AsyncMock()
            result = await _collector().run()

        assert result.status == CollectStatus.PARTIAL
        assert result.errors is not None and len(result.errors) == 2

    async def test_failure_propagates_as_failed_result(self) -> None:
        with (
            patch("collector.spiders.kb_index.AsyncSessionLocal") as mock_factory,
            patch(
                "collector.spiders.kb_index.index_service.run_index",
                new=AsyncMock(side_effect=RuntimeError("db_down")),
            ),
        ):
            mock_factory.return_value.__aenter__.return_value = AsyncMock()
            result = await _collector().run()

        assert result.status == CollectStatus.FAILED
        assert result.errors == ["db_down"]
