"""Tests for Celery app queue routing and task option resolution."""

from unittest.mock import patch

import pytest

from collector.celery_app import QUEUE_DEFAULTS, resolve_queue, resolve_task_options
from collector.runtime.registry import TASK_SPECS


@pytest.mark.unit
class TestResolveQueue:
    def test_default_queue_is_batch(self) -> None:
        assert resolve_queue("unknown-task") == "collector.batch"

    def test_task_spec_queue_override(self) -> None:
        assert resolve_queue("quote") == "collector.realtime"
        assert resolve_queue("financial-report") == "collector.heavy"

    def test_source_does_not_influence_queue(self) -> None:
        assert resolve_queue("fund-flow", preferred_source="eastmoney") == "collector.batch"

    def test_explicit_collector_task_queue_wins(self) -> None:
        with patch("collector.celery_app.TASK_SPECS", {}):
            assert resolve_queue("fund-flow") == "collector.batch"


@pytest.mark.unit
class TestResolveTaskOptions:
    def test_defaults_derived_from_queue(self) -> None:
        options = resolve_task_options("quote")
        assert options["queue"] == "collector.realtime"
        assert options["soft_time_limit"] == QUEUE_DEFAULTS["collector.realtime"]["soft_time_limit"]
        assert options["max_retries"] == QUEUE_DEFAULTS["collector.realtime"]["max_retries"]
        assert "retry_backoff" in options

    def test_spec_overrides_soft_time_limit_and_retries(self) -> None:
        spec = TASK_SPECS["financial-report"]
        assert spec.soft_time_limit is None or isinstance(spec.soft_time_limit, int)

        options = resolve_task_options("financial-report")
        assert options["queue"] == "collector.heavy"
        assert options["soft_time_limit"] == QUEUE_DEFAULTS["collector.heavy"]["soft_time_limit"]

    def test_queue_override_takes_precedence(self) -> None:
        options = resolve_task_options("quote", queue_override="collector.heavy")
        assert options["queue"] == "collector.heavy"
        assert options["soft_time_limit"] == QUEUE_DEFAULTS["collector.heavy"]["soft_time_limit"]

    def test_source_does_not_influence_options(self) -> None:
        options = resolve_task_options("sector-fund-flow", preferred_source="eastmoney")
        assert options["queue"] == "collector.batch"
