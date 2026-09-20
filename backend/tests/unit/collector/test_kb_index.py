"""知识库索引采集器测试（internal 薄壳委托 index_service）。"""

from unittest.mock import AsyncMock, patch

import pytest

from collector.core.base import CollectStatus
from collector.spiders.kb_index import KbIndexCollector


def _collector() -> KbIndexCollector:
    return KbIndexCollector({"source": "internal", "data_type": "kb_index"})


@pytest.mark.unit
class TestKbIndexRun:
    async def test_indexed_reports_success(self) -> None:
        stats = {"pointsIndexed": 3, "segmentsIndexed": 10, "imagesIndexed": 2}
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
        assert result.items_stored == 15
        assert result.metadata == stats
        assert p_run.call_args.kwargs["force_rebuild"] is False

    async def test_nothing_dirty_is_benign_skipped(self) -> None:
        stats = {"nothingDirty": 1}
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
        assert "没有待索引变更" in (result.message or "")

    async def test_fingerprint_mismatch_skips_with_hint(self) -> None:
        stats = {"fingerprintMismatch": 1}
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
        assert "force_rebuild" in (result.message or "")

    async def test_force_rebuild_param_forwarded(self) -> None:
        stats = {"rebuildVersion": 2, "pointsIndexed": 1}
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
            "pointsIndexed": 1,
            "segmentsIndexed": 0,
            "imagesIndexed": 0,
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
                new=AsyncMock(side_effect=RuntimeError("es_down")),
            ),
        ):
            mock_factory.return_value.__aenter__.return_value = AsyncMock()
            result = await _collector().run()

        assert result.status == CollectStatus.FAILED
        assert result.errors == ["es_down"]
