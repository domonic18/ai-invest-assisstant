"""盘中计划校准采集器契约测试（时段门控/窗口推导/Agent 循环隔离/幂等留痕）。"""

from contextlib import ExitStack
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.trading.agent_plan_calibration import CalibrationLockedError
from collector.core.base import CollectStatus
from collector.spiders.agent_plan_calibration import AgentPlanCalibrationCollector

_DATE = date(2026, 9, 30)  # Wednesday


def _agent(key: str = "short-line") -> SimpleNamespace:
    return SimpleNamespace(agent_key=key)


def _summary(**overrides: object) -> dict:
    base: dict = {
        "cached": False,
        "window": "1020",
        "total": 3,
        "maintain": 1,
        "adjust": 1,
        "cancel": 1,
        "applied": 0,
        "shadow": 3,
        "rejected": 0,
        "new_plan_ids": [],
    }
    base.update(overrides)
    return base


def _collector() -> AgentPlanCalibrationCollector:
    return AgentPlanCalibrationCollector(
        {"source": "internal", "data_type": "agent-plan-calibration"}
    )


def _patch_env(
    *,
    trading_day: bool = True,
    in_session: bool = True,
    hour: int = 10,
    agents: list | None = None,
    codes: set[str] | None = None,
    calibrate: AsyncMock | None = None,
):
    """统一打桩：日历/时段/会话工厂/注册表/行情/校准服务。"""
    agent_rows = agents if agents is not None else [_agent()]
    return (
        patch(
            "collector.spiders.agent_plan_calibration.is_trading_day",
            return_value=trading_day,
        ),
        patch(
            "collector.spiders.agent_plan_calibration.in_trading_session",
            return_value=in_session,
        ),
        patch(
            "collector.spiders.agent_plan_calibration.now_cn",
            return_value=SimpleNamespace(hour=hour),
        ),
        patch(
            "collector.spiders.agent_plan_calibration.latest_trading_day",
            return_value=_DATE,
        ),
        patch("collector.spiders.agent_plan_calibration.AsyncSessionLocal"),
        patch(
            "collector.spiders.agent_plan_calibration.agent_registry.get_calibration_agents",
            AsyncMock(return_value=agent_rows),
        ),
        patch(
            "collector.spiders.agent_plan_calibration.agent_registry.get_active_agent",
            AsyncMock(side_effect=lambda _s, key: _agent(key)),
        ),
        patch(
            "collector.spiders.agent_plan_calibration.agent_intraday_service.plan_stock_codes",
            AsyncMock(return_value=codes if codes is not None else {"600000", "000001"}),
        ),
        patch(
            "collector.spiders.agent_plan_calibration.fetch_sina_quotes",
            MagicMock(return_value={"600000": {"price": 10.0}}),
        ),
        patch(
            "collector.spiders.agent_plan_calibration.run_calibration",
            calibrate or AsyncMock(return_value=_summary()),
        ),
    )


def _activate(patches):
    """在单个 with 块内启用全部 patch。"""
    stack = ExitStack()
    for p in patches:
        stack.enter_context(p)
    return stack


@pytest.mark.unit
class TestAgentPlanCalibrationCollector:
    @pytest.mark.asyncio
    async def test_skips_non_trading_day(self) -> None:
        patches = _patch_env(trading_day=False)
        with patches[0]:
            result = await _collector().run()

        assert result.status == CollectStatus.SKIPPED
        assert "不是交易日" in (result.message or "")

    @pytest.mark.asyncio
    async def test_skips_outside_trading_session(self) -> None:
        """校准是盘中一次性语义：盘外（含手动补跑）整体 SKIPPED。"""
        patches = _patch_env(in_session=False)
        with _activate(patches[:2]):
            result = await _collector().run()

        assert result.status == CollectStatus.SKIPPED
        assert "非盘中执行时段" in (result.message or "")

    @pytest.mark.asyncio
    async def test_skips_when_no_calibration_agents(self) -> None:
        with _activate(_patch_env(agents=[])):
            result = await _collector().run()

        assert result.status == CollectStatus.SKIPPED
        assert "无启用盘中校准" in (result.message or "")

    @pytest.mark.asyncio
    async def test_success_prefetches_quotes_and_reports_counts(self) -> None:
        calibrate = AsyncMock(return_value=_summary())
        with _activate(_patch_env(calibrate=calibrate)):
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        assert result.items_collected == 1
        assert result.items_stored == 3  # applied + shadow + rejected
        assert "修正单 3 条" in (result.message or "")
        assert result.metadata["window"] == "1020"
        assert result.metadata["trade_date"] == _DATE.isoformat()
        calibrate.assert_awaited_once()
        assert calibrate.await_args.args[3] == "1020"
        assert calibrate.await_args.kwargs["quotes"] == {"600000": {"price": 10.0}}

    @pytest.mark.asyncio
    async def test_afternoon_wall_clock_derives_afternoon_window(self) -> None:
        """无显式 window 时按北京墙钟推导：13:30 → 午盘 1320。"""
        calibrate = AsyncMock(return_value=_summary())
        with _activate(_patch_env(calibrate=calibrate, hour=13)):
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        assert result.metadata["window"] == "1320"
        assert calibrate.await_args.args[3] == "1320"

    @pytest.mark.asyncio
    async def test_cached_and_locked_agents_recorded_in_message(self) -> None:
        """幂等命中与锁冲突都是良性留痕（真实短形状无计数键），不算失败。"""

        async def _calibrate(_s, agent, *_args, **kwargs):
            if agent.agent_key == "short-line":
                return {"cached": True, "window": "1020", "total": 0}
            raise CalibrationLockedError()

        with _activate(_patch_env(agents=[_agent("short-line"), _agent("m60")], calibrate=AsyncMock(side_effect=_calibrate))):
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        assert result.items_stored == 0
        assert "已校准" in (result.message or "")
        assert "正在执行中" in (result.message or "")

    @pytest.mark.asyncio
    async def test_skipped_reason_short_summary_counts_zero(self) -> None:
        """无当日计划的真实短形状（仅 skipped_reason，无计数键）不能让汇总崩溃。"""

        async def _calibrate(_s, agent, *_args, **kwargs):
            return {
                "cached": False,
                "window": "1320",
                "total": 0,
                "skipped_reason": "无当日活跃计划",
            }

        with _activate(_patch_env(agents=[_agent("short-line")], calibrate=AsyncMock(side_effect=_calibrate))):
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        assert result.items_stored == 0
        assert "无当日活跃计划" in (result.message or "")

    @pytest.mark.asyncio
    async def test_single_agent_error_is_partial(self) -> None:
        """单 Agent 异常隔离：另一个成功 → PARTIAL，错误进 errors。"""

        async def _calibrate(_s, agent, *_args, **kwargs):
            if agent.agent_key == "short-line":
                raise ValueError("LLM 超时")
            return _summary()

        with _activate(
            _patch_env(agents=[_agent("short-line"), _agent("m60")], calibrate=AsyncMock(side_effect=_calibrate))
        ):
            result = await _collector().run()

        assert result.status == CollectStatus.PARTIAL
        assert any("LLM 超时" in err for err in result.errors)
