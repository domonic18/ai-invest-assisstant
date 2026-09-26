"""交易 Agent 总览聚合服务测试（D28：next_tasks 按 plan/review_cadence 门控）。"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.trading import agent_overview_service as svc


def _session(schedules: list[SimpleNamespace]) -> MagicMock:
    session = MagicMock()
    ret = MagicMock()
    ret.all.return_value = schedules
    session.scalars = AsyncMock(return_value=ret)
    return session


def _row(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "agent_key": "short-line",
        "plan_cadence": "daily",
        "review_cadence": "daily",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.unit
class TestCadenceDue:
    @pytest.mark.asyncio
    async def test_daily_requires_trading_day_only(self) -> None:
        with patch(
            "app.services.market.trade_calendar_service.is_trading_day",
            AsyncMock(return_value=True),
        ):
            assert (
                await svc._cadence_due(MagicMock(), "daily", datetime(2026, 9, 28).date())
                is True
            )

    @pytest.mark.asyncio
    async def test_non_trading_day_never_due(self) -> None:
        with patch(
            "app.services.market.trade_calendar_service.is_trading_day",
            AsyncMock(return_value=False),
        ):
            assert (
                await svc._cadence_due(MagicMock(), "daily", datetime(2026, 9, 26).date())
                is False
            )

    @pytest.mark.asyncio
    async def test_weekly_requires_period_end(self) -> None:
        with (
            patch(
                "app.services.market.trade_calendar_service.is_trading_day",
                AsyncMock(return_value=True),
            ),
            patch(
                "app.services.trading.agent_review_service.is_last_trading_day_of_week",
                AsyncMock(return_value=False),
            ),
        ):
            assert (
                await svc._cadence_due(MagicMock(), "weekly", datetime(2026, 9, 28).date())
                is False
            )


@pytest.mark.unit
class TestNextTaskTimes:
    @pytest.mark.asyncio
    async def test_returns_sorted_utc_tasks_for_daily_agent(self) -> None:
        session = _session(
            [
                SimpleNamespace(
                    task_name="agent_daily_plan_1900", schedule="0 19 * * 1-5"
                ),
                SimpleNamespace(
                    task_name="paper_trade_review_1610", schedule="0 16 * * 1-5"
                ),
            ]
        )
        row = _row()
        with patch(
            "app.services.market.trade_calendar_service.is_trading_day",
            AsyncMock(return_value=True),
        ):
            tasks = await svc._next_task_times(session, row)
        assert [t.task for t in tasks] == ["模拟盘分层复盘", "每日选股与交易计划"]
        assert all(t.scheduled_at.tzinfo == timezone.utc for t in tasks)

    @pytest.mark.asyncio
    async def test_weekly_agent_waits_for_due_candidate(self) -> None:
        """weekly 门控：非周期日候选被跳过，直到命中 due 候选（下周五 19:00）。"""
        session = _session(
            [SimpleNamespace(task_name="agent_daily_plan_1900", schedule="0 19 * * 1-5")]
        )
        row = _row(plan_cadence="weekly")

        async def _due(_s: object, cadence: str, day: object) -> bool:
            return cadence == "weekly" and day.isoweekday() == 5

        with patch.object(svc, "_cadence_due", _due):
            tasks = await svc._next_task_times(session, row)

        assert len(tasks) == 1
        assert tasks[0].scheduled_at.isoweekday() == 5

    @pytest.mark.asyncio
    async def test_never_due_task_is_omitted(self) -> None:
        session = _session(
            [
                SimpleNamespace(task_name="agent_daily_plan_1900", schedule="0 19 * * 1-5"),
                SimpleNamespace(task_name="paper_trade_review_1610", schedule="0 16 * * 1-5"),
            ]
        )
        row = _row()

        async def _never_due(_s: object, cadence: str, day: object) -> bool:
            return False

        with patch.object(svc, "_cadence_due", _never_due):
            tasks = await svc._next_task_times(session, row)

        assert tasks == []

    @pytest.mark.asyncio
    async def test_inactive_or_blank_schedule_omitted(self) -> None:
        session = _session(
            [SimpleNamespace(task_name="agent_daily_plan_1900", schedule="")]
        )
        tasks = await svc._next_task_times(session, _row())
        assert tasks == []
