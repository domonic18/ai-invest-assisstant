"""collector runtime runner 契约测试（统一执行入口与日志落库）。"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from collector.core.base import CollectResult, CollectStatus
from collector.runtime.registry import TASK_MAP
from collector.runtime.runner import (
    _ERROR_MSG_MAX_LEN,
    _build_task_kwargs,
    _mark_running,
    _persist_error,
    _persist_result,
    _precheck_trade_day,
    run_task,
)


def _noop_precheck():
    """既有 run_task 用例统一旁路预检（预检行为在 TestTradeDayPrecheck 单测）。"""
    return patch(
        "collector.runtime.runner._precheck_trade_day", AsyncMock(return_value=None)
    )


def _make_result() -> CollectResult:
    now = datetime.now(timezone.utc)
    return CollectResult(
        source="cninfo",
        data_type="financial_report",
        status=CollectStatus.SUCCESS,
        items_collected=2,
        items_stored=2,
        errors=[],
        started_at=now,
        finished_at=now,
    )


def _mock_session(mock_log: MagicMock | None) -> MagicMock:
    mock_session = AsyncMock()
    mock_session.get.return_value = mock_log
    return MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_session),
            __aexit__=AsyncMock(return_value=None),
        )
    )


@pytest.mark.unit
class TestBuildTaskKwargs:
    def test_kline(self) -> None:
        kwargs = _build_task_kwargs("kline", {"period": "weekly"})
        assert kwargs == {"period": "weekly"}

    def test_financial_report(self) -> None:
        kwargs = _build_task_kwargs(
            "financial-report",
            {
                "symbols": ["000001"],
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "report_types": ["年报"],
                "preferred_source": "cninfo",
            },
        )
        assert kwargs["symbols"] == ["000001"]
        assert kwargs["start_date"] == "2024-01-01"
        assert kwargs["end_date"] == "2024-12-31"
        assert kwargs["report_types"] == ["年报"]
        assert kwargs["preferred_source"] == "cninfo"

    def test_none_values_are_skipped(self) -> None:
        kwargs = _build_task_kwargs("kline", {"period": None, "symbols": None})
        assert kwargs == {}


@pytest.mark.unit
class TestTaskEntryDefaults:
    @pytest.mark.asyncio
    async def test_sector_kline_defaults_apply_on_scheduled_path(self) -> None:
        """定时路径无请求参数：run_params 缺省须由 TaskSpec.defaults 兜底，
        不得把 None 透传给采集器（曾致 sector-kline 每日 int(None) 崩溃）。"""
        captured: dict = {}

        async def fake_run(
            task_name: str,
            data_type: str,
            collector_map: dict,
            preferred_source: str | None,
            **kwargs: object,
        ) -> CollectResult:
            captured.update(kwargs)
            return _make_result()

        with patch(
            "collector.runtime.registry._run_collector_for_task",
            side_effect=fake_run,
        ):
            await TASK_MAP["sector-kline"]()

        assert captured["lookback_days"] == 10


@pytest.mark.unit
class TestRunTask:
    @pytest.mark.asyncio
    async def test_run_task_executes_and_persists(self) -> None:
        result = _make_result()
        mock_task = AsyncMock(return_value=result)
        precheck = _noop_precheck()

        with (
            precheck,
            patch(
                "collector.runtime.runner.TASK_MAP", {"financial-report": mock_task}
            ),
            patch(
                "collector.runtime.runner._create_running_row", AsyncMock(return_value=55)
            ),
            patch(
                "collector.runtime.runner._persist_result", AsyncMock()
            ) as mock_persist,
        ):
            outcome = await run_task({"task": "financial-report", "log_id": None})

        assert outcome is result
        mock_task.assert_awaited_once()
        (
            task_name,
            log_id,
            celery_task_id,
            task_run_id,
            persisted,
        ) = mock_persist.await_args.args
        assert task_name == "financial-report"
        # beat/定时路径无预建行：执行前落的 running 行 id 复用给终态更新
        assert log_id == 55
        assert celery_task_id is None
        assert len(task_run_id) == 8
        assert persisted is result

    @pytest.mark.asyncio
    async def test_run_task_marks_running_when_log_id(self) -> None:
        result = _make_result()
        precheck = _noop_precheck()
        with (
            precheck,
            patch(
                "collector.runtime.runner.TASK_MAP",
                {"financial-report": AsyncMock(return_value=result)},
            ),
            patch(
                "collector.runtime.runner._mark_running", AsyncMock()
            ) as mock_running,
            patch(
                "collector.runtime.runner._create_running_row", AsyncMock()
            ) as mock_create,
            patch("collector.runtime.runner._persist_result", AsyncMock()),
        ):
            await run_task({"task": "financial-report", "log_id": 7})

        mock_running.assert_awaited_once_with(7)
        mock_create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_run_task_creates_running_row_for_beat_path(self) -> None:
        """无 log_id（beat 派发）时执行前落 running 行——挂死任务在日志页可见。"""
        result = _make_result()
        precheck = _noop_precheck()
        with (
            precheck,
            patch("collector.runtime.runner.TASK_MAP", {"financial-report": AsyncMock(return_value=result)}),
            patch(
                "collector.runtime.runner._create_running_row", AsyncMock(return_value=66)
            ) as mock_create,
            patch(
                "collector.runtime.runner._persist_result", AsyncMock()
            ) as mock_persist,
        ):
            await run_task({"task": "financial-report", "log_id": None})

        mock_create.assert_awaited_once_with("financial-report", None)
        assert mock_persist.await_args.args[1] == 66

    @pytest.mark.asyncio
    async def test_unknown_task_raises_and_persists_error(self) -> None:
        with patch(
            "collector.runtime.runner._persist_error", AsyncMock()
        ) as mock_error:
            with pytest.raises(ValueError, match="Unknown task"):
                await run_task({"task": "nope", "log_id": 9})

        mock_error.assert_awaited_once()
        assert mock_error.await_args.args[0] == 9

    @pytest.mark.asyncio
    async def test_missing_task_raises(self) -> None:
        with pytest.raises(ValueError, match="Missing required field"):
            await run_task({})


@pytest.mark.unit
class TestLogPersistence:
    @pytest.mark.asyncio
    async def test_mark_running(self) -> None:
        mock_log = MagicMock()
        with patch(
            "collector.runtime.runner.AsyncSessionLocal",
            _mock_session(mock_log),
        ):
            await _mark_running(1)

        assert mock_log.status == "running"
        assert isinstance(mock_log.started_at, datetime)

    @pytest.mark.asyncio
    async def test_persist_result_updates_existing_row(self) -> None:
        mock_log = MagicMock()
        mock_log.meta = {"task": "financial-report"}
        mock_session = AsyncMock()
        mock_session.get.return_value = mock_log
        session_factory = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_session),
                __aexit__=AsyncMock(return_value=None),
            )
        )

        with patch(
            "collector.runtime.runner.AsyncSessionLocal", session_factory
        ):
            await _persist_result(
                "financial-report", 1, None, "abcd1234", _make_result()
            )

        assert mock_log.status == "success"
        assert mock_log.source == "cninfo"
        assert mock_log.records_count == 2
        assert mock_log.meta["task_run_id"] == "abcd1234"
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_persist_result_inserts_row_without_log_id(self) -> None:
        mock_session = MagicMock()
        mock_session.commit = AsyncMock()
        session_factory = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_session),
                __aexit__=AsyncMock(return_value=None),
            )
        )

        with patch(
            "collector.runtime.runner.AsyncSessionLocal", session_factory
        ):
            await _persist_result(
                "financial-report", None, None, "abcd1234", _make_result()
            )

        mock_session.add.assert_called_once()
        added = mock_session.add.call_args.args[0]
        assert added.task_name == "financial-report"
        assert added.status == "success"
        assert added.meta["task_run_id"] == "abcd1234"
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_persist_result_skip_message_not_in_error(self) -> None:
        """SKIPPED 说明落 message 列，error_msg 保持为空（日志页红字只留错误）。"""
        result = CollectResult(
            source="internal",
            data_type="kb_transcribe",
            status=CollectStatus.SKIPPED,
            message="没有待转写素材（队列为空或全部忙）",
        )
        mock_log = MagicMock()
        with patch(
            "collector.runtime.runner.AsyncSessionLocal",
            _mock_session(mock_log),
        ):
            await _persist_result("kb-transcribe", 1, None, "abcd1234", result)

        assert mock_log.status == "skipped"
        assert mock_log.message == "没有待转写素材（队列为空或全部忙）"
        assert mock_log.error_msg is None

    @pytest.mark.asyncio
    async def test_persist_error_records_traceback_truncated(self) -> None:
        mock_log = MagicMock()
        with patch(
            "collector.runtime.runner.AsyncSessionLocal",
            _mock_session(mock_log),
        ):
            try:
                raise ValueError("x" * 10000)
            except ValueError as exc:
                await _persist_error(1, None, exc)

        assert mock_log.status == "failed"
        assert "ValueError" in mock_log.error_msg
        assert "Traceback" in mock_log.error_msg
        assert len(mock_log.error_msg) <= _ERROR_MSG_MAX_LEN


def _mock_precheck_session(trade_day_only: bool | None) -> MagicMock:
    mock_session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = trade_day_only
    mock_session.execute.return_value = result
    return MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_session),
            __aexit__=AsyncMock(return_value=None),
        )
    )


@pytest.mark.unit
class TestTradeDayPrecheck:
    """trade_day_only 调度预检：非交易日/日历未覆盖 SKIPPED，显式日期豁免。"""

    _SPEC = MagicMock(data_type="kline")

    async def _run_precheck(
        self,
        trade_day_only: bool | None,
        verdict: str,
        params: dict | None = None,
        kwargs: dict | None = None,
    ) -> CollectResult | None:
        with (
            patch(
                "collector.runtime.runner.AsyncSessionLocal",
                _mock_precheck_session(trade_day_only),
            ),
            patch(
                "collector.runtime.runner.classify_schedule_day",
                AsyncMock(return_value=verdict),
            ),
            patch(
                "collector.runtime.runner.today_cn",
                lambda: datetime(2026, 9, 25).date(),  # 周五
            ),
        ):
            return await _precheck_trade_day(
                params or {"preferred_source": "ths"},
                kwargs or {},
                self._SPEC,
                "ths_kline_daily",
            )

    @pytest.mark.asyncio
    async def test_not_trade_day_only_passes(self) -> None:
        assert await self._run_precheck(False, "non_trading") is None

    @pytest.mark.asyncio
    async def test_no_task_row_passes(self) -> None:
        assert await self._run_precheck(None, "trading") is None

    @pytest.mark.asyncio
    async def test_trading_day_passes(self) -> None:
        assert await self._run_precheck(True, "trading") is None

    @pytest.mark.asyncio
    async def test_non_trading_day_skips_with_message(self) -> None:
        result = await self._run_precheck(True, "non_trading")
        assert result is not None
        assert result.status == CollectStatus.SKIPPED
        assert result.message is not None and "非交易日" in result.message
        assert result.source == "ths"
        assert result.data_type == "kline"

    @pytest.mark.asyncio
    async def test_unknown_calendar_skips_with_calendar_message(self) -> None:
        """D5：日历未覆盖拒绝调度，message 注明（不静默回退周末启发）。"""
        result = await self._run_precheck(True, "unknown")
        assert result is not None
        assert result.status == CollectStatus.SKIPPED
        assert result.message is not None and "未覆盖" in result.message

    @pytest.mark.asyncio
    async def test_explicit_trade_date_exempts_without_db(self) -> None:
        with patch(
            "collector.runtime.runner.AsyncSessionLocal"
        ) as mock_factory:
            result = await _precheck_trade_day(
                {}, {"trade_date": "2026-09-25"}, self._SPEC, "ths_kline_daily"
            )
        assert result is None
        mock_factory.assert_not_called()

    @pytest.mark.asyncio
    async def test_explicit_backfill_range_exempts(self) -> None:
        result = await self._run_precheck(
            True,
            "non_trading",
            kwargs={"start_date": "2026-09-01", "end_date": "2026-09-20"},
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_beat_instance_name_used_for_lookup(self) -> None:
        """beat 传实例名（task_name）；实例名优先于任务类型名。"""
        with (
            patch(
                "collector.runtime.runner.AsyncSessionLocal",
                _mock_precheck_session(True),
            ),
            patch(
                "collector.runtime.runner.classify_schedule_day",
                AsyncMock(return_value="trading"),
            ),
            patch(
                "collector.runtime.runner.today_cn",
                lambda: datetime(2026, 9, 25).date(),
            ),
        ):
            result = await _precheck_trade_day(
                {"task": "kline", "task_name": "ths_kline_daily"},
                {},
                self._SPEC,
                "kline",
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_run_task_short_circuits_on_precheck_skip(self) -> None:
        """预检 SKIPPED：任务体不执行，日志按 skipped 终态持久化。"""
        skipped = CollectResult(
            source="internal",
            data_type="kline",
            status=CollectStatus.SKIPPED,
            message="非交易日，按 trade_day_only 预检跳过",
        )
        mock_task = AsyncMock(return_value=_make_result())
        with (
            patch(
                "collector.runtime.runner._precheck_trade_day",
                AsyncMock(return_value=skipped),
            ),
            patch(
                "collector.runtime.runner._create_running_row",
                AsyncMock(return_value=77),
            ),
            patch(
                "collector.runtime.runner._persist_result", AsyncMock()
            ) as mock_persist,
            patch("collector.runtime.runner.TASK_MAP", {"kline": mock_task}),
        ):
            outcome = await run_task({"task": "kline", "log_id": None})

        assert outcome is skipped
        mock_task.assert_not_awaited()  # 不进入任务体执行
        persisted = mock_persist.await_args.args[4]
        assert persisted.status == CollectStatus.SKIPPED
        assert mock_persist.await_args.args[1] == 77
