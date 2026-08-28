"""Tests for Celery app queue routing, task option resolution, and worker lifecycle."""

from unittest.mock import MagicMock, patch

import pytest

from collector.celery_app import (
    QUEUE_DEFAULTS,
    _init_worker_process,
    resolve_queue,
    resolve_task_options,
)
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


@pytest.mark.unit
class TestInitWorkerProcess:
    def test_disposes_and_recreates_app_engine(self) -> None:
        old_engine = MagicMock()
        old_engine.url.render_as_string.return_value = "postgresql+asyncpg://user:pass@db/db"
        old_engine.echo = False

        new_engine = MagicMock()
        session_maker = MagicMock()

        app_database = MagicMock()
        app_database.engine = old_engine
        app_database.AsyncSessionLocal = session_maker

        with patch("app.core.database", app_database):
            with patch("collector.core.base.dispose_engine"):
                with patch("collector.core.logging.configure_logging"):
                    with patch("structlog.get_logger"):
                        with patch("sqlalchemy.ext.asyncio.create_async_engine", return_value=new_engine) as mock_create:
                            with patch("asyncio.run"):
                                _init_worker_process()

        old_engine.sync_engine.dispose.assert_called_once_with(close=False)
        old_engine.dispose.assert_called_once()
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["pool_pre_ping"] is True
        assert app_database.engine is new_engine
        session_maker.configure.assert_called_once_with(bind=new_engine)

    def test_disposes_collector_engine(self) -> None:
        old_engine = MagicMock()
        old_engine.url.render_as_string.return_value = "postgresql+asyncpg://user:pass@db/db"
        old_engine.echo = False

        app_database = MagicMock()
        app_database.engine = old_engine
        app_database.AsyncSessionLocal = MagicMock()

        dispose_engine_mock = MagicMock()

        with patch("app.core.database", app_database):
            with patch("collector.core.base.dispose_engine", dispose_engine_mock):
                with patch("collector.core.logging.configure_logging"):
                    with patch("structlog.get_logger"):
                        with patch("sqlalchemy.ext.asyncio.create_async_engine", return_value=MagicMock()):
                            with patch("asyncio.run"):
                                _init_worker_process()

        dispose_engine_mock.assert_called_once()
