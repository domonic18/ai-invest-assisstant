"""Celery app 契约测试：队列路由、任务选项解析与 worker 生命周期。"""

import logging
import sys
from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest

from collector.celery_app import (
    QUEUE_DEFAULTS,
    _init_worker_process,
    app,
    resolve_queue,
    resolve_task_options,
)
from collector.core.logging import configure_logging
from collector.runtime.registry import TASK_SPECS


@pytest.mark.unit
class TestResolveQueue:
    def test_default_queue_is_batch(self) -> None:
        assert resolve_queue("unknown-task") == "collector.batch"

    def test_task_spec_queue_override(self) -> None:
        assert resolve_queue("quote") == "collector.realtime"
        assert resolve_queue("financial-report") == "collector.heavy"
        assert resolve_queue("limit-up-ai-review") == "collector.heavy"

    def test_source_does_not_influence_queue(self) -> None:
        assert resolve_queue("fund-flow", preferred_source="eastmoney") == "collector.batch"

    def test_explicit_collector_task_queue_wins(self) -> None:
        with patch("collector.celery_app.TASK_SPECS", {}):
            assert resolve_queue("fund-flow") == "collector.batch"


@pytest.mark.unit
class TestResolveTaskOptions:
    def test_options_keys_are_celery_valid(self) -> None:
        """出口键名钉死：apply_async 硬时限只认 ``time_limit``——
        ``hard_time_limit`` 会被 celery 静默忽略（2026-09-23 挂死事故根因）。
        """
        options = resolve_task_options("quote")
        assert set(options) == {
            "queue",
            "soft_time_limit",
            "time_limit",
            "max_retries",
            "retry_backoff",
            "retry_backoff_max",
        }
        assert "hard_time_limit" not in options

    def test_defaults_derived_from_queue(self) -> None:
        options = resolve_task_options("quote")
        defaults = QUEUE_DEFAULTS["collector.realtime"]
        assert options["queue"] == "collector.realtime"
        assert options["soft_time_limit"] == defaults["soft_time_limit"]
        assert options["time_limit"] == defaults["time_limit"]
        assert options["max_retries"] == defaults["max_retries"]
        assert options["retry_backoff"] == defaults["retry_backoff"]
        assert options["retry_backoff_max"] == defaults["retry_backoff_max"]

    def test_unknown_task_falls_back_to_batch_defaults(self) -> None:
        options = resolve_task_options("no-such-task")
        defaults = QUEUE_DEFAULTS["collector.batch"]
        assert options["queue"] == "collector.batch"
        assert options["time_limit"] == defaults["time_limit"]
        assert options["max_retries"] == defaults["max_retries"]

    def test_spec_overrides_soft_time_limit_and_retries(self) -> None:
        spec = TASK_SPECS["financial-report"]
        assert spec.soft_time_limit is None or isinstance(spec.soft_time_limit, int)

        options = resolve_task_options("financial-report")
        assert options["queue"] == "collector.heavy"
        assert options["soft_time_limit"] == QUEUE_DEFAULTS["collector.heavy"]["soft_time_limit"]

    def test_spec_overrides_hard_time_limit(self) -> None:
        spec = replace(TASK_SPECS["quote"], hard_time_limit=90)
        with patch("collector.celery_app.TASK_SPECS", {**TASK_SPECS, "quote": spec}):
            options = resolve_task_options("quote")

        assert options["time_limit"] == 90
        assert options["soft_time_limit"] == QUEUE_DEFAULTS["collector.realtime"]["soft_time_limit"]

    def test_retry_backoff_max_is_explicit_not_borrowed_hard_limit(self) -> None:
        assert QUEUE_DEFAULTS["collector.realtime"]["retry_backoff_max"] == 300
        assert QUEUE_DEFAULTS["collector.batch"]["retry_backoff_max"] == 600
        assert QUEUE_DEFAULTS["collector.heavy"]["retry_backoff_max"] == 1800
        options = resolve_task_options("market-daily-review")
        assert options["retry_backoff_max"] == 1800

    def test_queue_override_takes_precedence(self) -> None:
        options = resolve_task_options("quote", queue_override="collector.heavy")
        assert options["queue"] == "collector.heavy"
        assert options["soft_time_limit"] == QUEUE_DEFAULTS["collector.heavy"]["soft_time_limit"]

    def test_source_does_not_influence_options(self) -> None:
        options = resolve_task_options("sector-fund-flow", preferred_source="eastmoney")
        assert options["queue"] == "collector.batch"


@pytest.mark.unit
class TestGlobalTimeLimitFallback:
    def test_conf_global_fallback_exceeds_max_per_message_limit(self) -> None:
        """全局兜底时限必须大于最长合法 per-message 硬限，否则会误杀合法长任务。"""
        max_spec_limit = max(
            spec.hard_time_limit
            for spec in TASK_SPECS.values()
            if spec.hard_time_limit is not None
        )
        max_queue_limit = max(d["time_limit"] for d in QUEUE_DEFAULTS.values())
        assert app.conf.task_soft_time_limit > max(max_spec_limit, max_queue_limit)
        assert app.conf.task_time_limit > app.conf.task_soft_time_limit


@pytest.mark.unit
class TestConfigureLogging:
    def test_binds_handler_to_startup_stdout_not_redirected_proxy(self) -> None:
        """celery 把 sys.stdout 换成 LoggingProxy 后，handler 仍须绑定真实 stdout。"""
        startup_stdout = sys.__stdout__
        proxy = MagicMock()
        root = logging.getLogger()
        saved_handlers = root.handlers[:]
        with patch.object(sys, "stdout", proxy):
            configure_logging()
            try:
                assert root.handlers
                assert root.handlers[0].stream is startup_stdout
                assert root.handlers[0].stream is not proxy
            finally:
                root.handlers = saved_handlers


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
