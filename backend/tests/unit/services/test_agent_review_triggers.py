"""按需复盘派发入口单测（B4）：周期/Agent/交易日校验 + 派发参数形状。"""

from contextlib import ExitStack
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import NotFoundError
from app.services.market.trade_calendar_service import NonTradingDayError
from app.services.trading.agent_review_triggers import (
    REVIEW_TASK_NAME,
    enqueue_review_generation,
)

_TRADE_DATE = date(2026, 7, 17)


def _patch_env(*, trading_day: bool = True, agent_missing: bool = False):
    """返回 (打桩栈, mocks)：日历/Agent 注册表/派发器全部替身。"""
    day_check = AsyncMock(return_value=trading_day)
    get_agent = AsyncMock(return_value=MagicMock(agent_key="short-line"))
    if agent_missing:
        get_agent.side_effect = NotFoundError("交易 Agent ghost 不存在")
    dispatch = AsyncMock(return_value=MagicMock(id=42, celery_task_id="celery-42"))

    stack = ExitStack()
    stack.enter_context(
        patch("app.services.trading.agent_review_triggers.is_trading_day", day_check)
    )
    stack.enter_context(patch("app.services.trading.agent_registry.get_agent", get_agent))
    stack.enter_context(
        patch("collector.runtime.dispatcher.dispatch_collector_task", dispatch)
    )
    return stack, {"day_check": day_check, "get_agent": get_agent, "dispatch": dispatch}


@pytest.mark.unit
class TestEnqueueReviewGeneration:
    @pytest.mark.asyncio
    async def test_dispatches_with_expected_params(self) -> None:
        stack, mocks = _patch_env()
        with stack:
            log = await enqueue_review_generation(
                MagicMock(),
                "short-line",
                period="quarter",
                trade_date=_TRADE_DATE,
                regenerate=True,
            )

        assert log.id == 42
        assert log.celery_task_id == "celery-42"
        mocks["get_agent"].assert_awaited_once()
        assert mocks["get_agent"].await_args.args[1] == "short-line"
        args = mocks["dispatch"].await_args.args
        assert args[1] == REVIEW_TASK_NAME
        assert args[2] == {
            "agent_key": "short-line",
            "period": "quarter",
            "regenerate": True,
            "trade_date": "2026-07-17",
        }

    @pytest.mark.asyncio
    async def test_omits_trade_date_when_absent(self) -> None:
        stack, mocks = _patch_env()
        with stack:
            await enqueue_review_generation(MagicMock(), "short-line", period="day")

        assert mocks["dispatch"].await_args.args[2] == {
            "agent_key": "short-line",
            "period": "day",
            "regenerate": False,
        }
        mocks["day_check"].assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_unknown_period_before_dispatch(self) -> None:
        stack, mocks = _patch_env()
        with stack:
            with pytest.raises(ValueError, match="未知复盘周期"):
                await enqueue_review_generation(
                    MagicMock(), "short-line", period="decade"
                )

        mocks["get_agent"].assert_not_awaited()
        mocks["dispatch"].assert_not_awaited()

    @pytest.mark.asyncio
    async def test_raises_when_agent_missing(self) -> None:
        stack, mocks = _patch_env(agent_missing=True)
        with stack:
            with pytest.raises(NotFoundError):
                await enqueue_review_generation(MagicMock(), "ghost", period="week")

        mocks["dispatch"].assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_non_trading_day(self) -> None:
        stack, mocks = _patch_env(trading_day=False)
        with stack:
            with pytest.raises(NonTradingDayError):
                await enqueue_review_generation(
                    MagicMock(), "short-line", period="month", trade_date=_TRADE_DATE
                )

        mocks["dispatch"].assert_not_awaited()
