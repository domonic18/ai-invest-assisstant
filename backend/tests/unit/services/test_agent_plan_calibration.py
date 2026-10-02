"""盘中计划校准服务测试（§11.5，D22）。

覆盖：观察报告聚合、run_calibration 门控（窗口/锁/幂等/无计划）、
shadow 只留痕不改计划、active 生效（adjust 推 version 自增 / cancel 置
cancelled / add 建新计划）、硬校验拒绝留痕（校准不是风控旁路）。
"""

from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import UnprocessableEntityError
from app.services.trading import agent_plan_calibration as cal
from app.services.trading.agent_plan_schemas import (
    PlanCalibrationContent,
    PlanCalibrationItem,
)

_DATE = date(2026, 9, 30)


def _plan(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "id": 1,
        "agent_key": "short-line",
        "plan_date": _DATE,
        "stock_code": "600000",
        "plan_type": "buy",
        "strategy": "s",
        "buy_zone_low": Decimal("9.80"),
        "buy_zone_high": Decimal("10.20"),
        "target_price": Decimal("11.00"),
        "stop_loss": Decimal("9.50"),
        "position_pct": Decimal("20.00"),
        "status": "active",
        "version": 1,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _agent(mode: str = "shadow", cap: str = "20") -> SimpleNamespace:
    return SimpleNamespace(
        agent_key="short-line",
        name="短线猎手",
        tagline="t",
        llm_config_id=None,
        calibration_mode=mode,
        risk_max_position_pct=Decimal(cap),
    )


def _item(**overrides: object) -> PlanCalibrationItem:
    base: dict[str, object] = {
        "action": "maintain",
        "stock_code": "600000",
        "reason": "r",
        "plan_type": None,
        "new_buy_zone_low": None,
        "new_buy_zone_high": None,
        "new_target_price": None,
        "new_stop_loss": None,
        "new_position_pct": None,
        "strategy": None,
    }
    base.update(overrides)
    return PlanCalibrationItem(**base)


def _content(items: list[PlanCalibrationItem]) -> PlanCalibrationContent:
    return PlanCalibrationContent(trade_date=_DATE.isoformat(), amendments=items)


def _session(
    scalar_values: list | None = None,
    plans: list | None = None,
    observations: list | None = None,
) -> MagicMock:
    """Mock 会话：scalar 按序返回（幂等计数/标的存在性）；scalars 按调用序
    弹出结果集（第一次=活跃计划查询，第二次=当日观测查询），耗尽回空。"""
    session = MagicMock()
    session.scalar = AsyncMock(side_effect=scalar_values or [0])
    result_queue = [plans or [], observations or []]

    def _scalars(*args: object, **kwargs: object) -> SimpleNamespace:
        rows = result_queue.pop(0) if result_queue else []
        return SimpleNamespace(all=MagicMock(return_value=rows))

    session.scalars = AsyncMock(side_effect=_scalars)
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


def _observation(stock_code: str, plan_id: int, **kw: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "stock_code": stock_code,
        "plan_id": plan_id,
        "action": "wait",
        "suppression_reason": None,
        "l0_verdict": "near_trigger",
        "market_snapshot": {"price": 10.0, "change_pct": 0.5},
    }
    base.update(kw)
    return SimpleNamespace(**base)


def _lock(acquired: bool = True):
    @asynccontextmanager
    async def _fake(*args: object, **kwargs: object):
        yield acquired

    return _fake


@pytest.mark.unit
class TestBuildObservationReport:
    async def test_aggregates_by_stock_code(self) -> None:
        rows = [
            _observation("600000", 1, action="wait"),
            _observation("600000", 1, action="execute", l0_verdict="triggered"),
            _observation(
                "000001", 2, suppression_reason="below_threshold", market_snapshot=None
            ),
        ]
        session = MagicMock()
        session.scalars = AsyncMock(
            return_value=SimpleNamespace(all=MagicMock(return_value=rows))
        )
        report = await cal.build_observation_report(session, "short-line", _DATE)
        by_code = {entry["stock_code"]: entry for entry in report}
        assert by_code["600000"]["ticks"] == 2
        assert by_code["600000"]["actions"] == {"wait": 1, "execute": 1}
        assert by_code["600000"]["verdicts"] == {"near_trigger": 1, "triggered": 1}
        assert by_code["600000"]["last_price"] == 10.0
        assert by_code["000001"]["suppressed"] == {"below_threshold": 1}
        assert by_code["000001"]["last_price"] is None

    async def test_empty_day_returns_empty_list(self) -> None:
        session = MagicMock()
        session.scalars = AsyncMock(
            return_value=SimpleNamespace(all=MagicMock(return_value=[]))
        )
        assert await cal.build_observation_report(session, "short-line", _DATE) == []


@pytest.mark.unit
class TestRunCalibration:
    async def test_invalid_window_rejected(self) -> None:
        with pytest.raises(UnprocessableEntityError):
            await cal.run_calibration(
                MagicMock(), _agent(), _DATE, "0930", quotes={}
            )

    async def test_lock_conflict_raises(self) -> None:
        with patch.object(cal, "redis_lock", _lock(acquired=False)):
            with pytest.raises(cal.CalibrationLockedError):
                await cal.run_calibration(MagicMock(), _agent(), _DATE, "1020", quotes={})

    async def test_cached_window_skips_llm(self) -> None:
        session = _session(scalar_values=[3])
        with (
            patch.object(cal, "redis_lock", _lock()),
            patch.object(cal, "_run_llm", AsyncMock()) as llm_mock,
        ):
            summary = await cal.run_calibration(session, _agent(), _DATE, "1020", quotes={})
        assert summary["cached"] is True
        llm_mock.assert_not_awaited()
        session.commit.assert_not_awaited()

    async def test_no_active_plans_skipped(self) -> None:
        session = _session(scalar_values=[0], plans=[])
        with (
            patch.object(cal, "redis_lock", _lock()),
            patch.object(cal, "_run_llm", AsyncMock()) as llm_mock,
        ):
            summary = await cal.run_calibration(session, _agent(), _DATE, "1320", quotes={})
        assert summary["skipped_reason"] == "无当日活跃计划"
        llm_mock.assert_not_awaited()

    async def test_shadow_records_without_mutating_plans(self) -> None:
        # 同窗口一码一单（uq 约束）：三计划三标的分别 maintain/adjust/cancel
        plan = _plan()
        plans = [plan, _plan(id=2, stock_code="000001"), _plan(id=3, stock_code="600519")]
        session = _session(scalar_values=[0], plans=plans)
        items = [
            _item(action="maintain"),
            _item(stock_code="000001", action="adjust", new_stop_loss=9.3),
            _item(stock_code="600519", action="cancel"),
        ]
        with (
            patch.object(cal, "redis_lock", _lock()),
            patch.object(cal, "_run_llm", AsyncMock(return_value=_content(items))),
        ):
            summary = await cal.run_calibration(
                session, _agent("shadow"), _DATE, "1020", quotes={"600000": {"price": 10.0}}
            )
        assert summary["total"] == 3
        assert summary["shadow"] == 3
        assert summary["applied"] == 0
        assert summary["rejected"] == 0
        assert plan.stop_loss == Decimal("9.50")  # 影子模式不改计划
        assert plan.version == 1
        assert plan.status == "active"
        rows = [call.args[0] for call in session.add.call_args_list]
        assert all(row.status == "shadow" for row in rows)
        session.commit.assert_awaited_once()

    async def test_active_adjust_bumps_version(self) -> None:
        plan = _plan()
        session = _session(scalar_values=[0], plans=[plan])
        items = [_item(action="adjust", new_buy_zone_low=9.6, new_stop_loss=9.2)]
        with (
            patch.object(cal, "redis_lock", _lock()),
            patch.object(cal, "_run_llm", AsyncMock(return_value=_content(items))),
        ):
            summary = await cal.run_calibration(
                session, _agent("active"), _DATE, "1020", quotes={"600000": {"price": 9.8}}
            )
        assert summary["applied"] == 1
        assert plan.buy_zone_low == Decimal("9.6")
        assert plan.stop_loss == Decimal("9.2")
        assert plan.version == 2
        assert plan.status == "active"
        row = session.add.call_args.args[0]
        assert row.status == "applied"

    async def test_active_cancel_marks_cancelled(self) -> None:
        plan = _plan()
        session = _session(scalar_values=[0], plans=[plan])
        with (
            patch.object(cal, "redis_lock", _lock()),
            patch.object(cal, "_run_llm", AsyncMock(return_value=_content([_item(action="cancel")]))),
        ):
            summary = await cal.run_calibration(
                session, _agent("active"), _DATE, "1020", quotes={}
            )
        assert summary["applied"] == 1
        assert plan.status == "cancelled"

    async def test_active_add_creates_new_plan(self) -> None:
        session = _session(scalar_values=[0, "600000"], plans=[_plan()])
        items = [
            _item(
                action="add",
                stock_code="000001",
                plan_type="buy",
                new_buy_zone_low=9.8,
                new_buy_zone_high=10.2,
                new_stop_loss=9.5,
                new_position_pct=15.0,
                strategy="尾盘回踩买点",
            )
        ]
        added: list[object] = []
        session.add = MagicMock(side_effect=added.append)

        async def _flush() -> None:
            for row in added:
                if isinstance(row, cal.AgentTradePlan) and row.id is None:
                    row.id = 99

        session.flush = AsyncMock(side_effect=_flush)
        with (
            patch.object(cal, "redis_lock", _lock()),
            patch.object(cal, "_run_llm", AsyncMock(return_value=_content(items))),
        ):
            summary = await cal.run_calibration(
                session, _agent("active"), _DATE, "1320", quotes={"000001": {"price": 10.0}}
            )
        assert summary["applied"] == 1
        assert summary["new_plan_ids"] == [99]
        new_plan = next(r for r in added if isinstance(r, cal.AgentTradePlan))
        assert new_plan.stock_code == "000001"
        assert new_plan.status == "active"
        assert "早盘校准" not in new_plan.basis  # 1320 = 午盘校准
        assert "午盘校准" in new_plan.basis
        assert added[-1].new_plan_id == 99

    async def test_adjust_without_new_values_rejected(self) -> None:
        plan = _plan()
        session = _session(scalar_values=[0], plans=[plan])
        items = [_item(action="adjust", reason="空调整")]
        with (
            patch.object(cal, "redis_lock", _lock()),
            patch.object(cal, "_run_llm", AsyncMock(return_value=_content(items))),
        ):
            summary = await cal.run_calibration(
                session, _agent("active"), _DATE, "1020", quotes={"600000": {"price": 10.0}}
            )
        assert summary["rejected"] == 1
        row = session.add.call_args.args[0]
        assert row.status == "rejected"
        assert "未携带任何新价位" in row.reject_reason
        assert plan.version == 1

    async def test_adjust_still_detached_rejected_by_sanity(self) -> None:
        """修正后仍远高于现价的计划被死单体检拒绝（校准不是旁路）。

        价位形状：下修区间 8.2~8.6 后 1.3×上沿=11.18 < 现价 14.0，追高体检命中。
        """
        plan = _plan(buy_zone_low=Decimal("12.0"), buy_zone_high=Decimal("12.5"), stop_loss=Decimal("11.5"))
        session = _session(scalar_values=[0], plans=[plan])
        items = [
            _item(
                action="adjust",
                new_buy_zone_low=8.2,
                new_buy_zone_high=8.6,
                new_stop_loss=7.8,
            )
        ]
        with (
            patch.object(cal, "redis_lock", _lock()),
            patch.object(cal, "_run_llm", AsyncMock(return_value=_content(items))),
        ):
            summary = await cal.run_calibration(
                session, _agent("active"), _DATE, "1020", quotes={"600000": {"price": 14.0}}
            )
        assert summary["rejected"] == 1
        row = session.add.call_args.args[0]
        assert "死单体检" in row.reject_reason

    async def test_add_over_position_cap_rejected(self) -> None:
        session = _session(scalar_values=[0, "600000"], plans=[_plan()])
        items = [
            _item(
                action="add",
                plan_type="buy",
                new_buy_zone_low=9.8,
                new_buy_zone_high=10.2,
                new_stop_loss=9.5,
                new_position_pct=35.0,
            )
        ]
        with (
            patch.object(cal, "redis_lock", _lock()),
            patch.object(cal, "_run_llm", AsyncMock(return_value=_content(items))),
        ):
            summary = await cal.run_calibration(
                session, _agent("active", cap="20"), _DATE, "1020", quotes={"600000": {"price": 10.0}}
            )
        assert summary["rejected"] == 1
        row = session.add.call_args.args[0]
        assert "超单票上限" in row.reject_reason

    async def test_add_unknown_code_rejected(self) -> None:
        session = _session(scalar_values=[0, None], plans=[_plan()])
        items = [
            _item(
                action="add",
                stock_code="999999",
                plan_type="buy",
                new_buy_zone_low=9.8,
                new_buy_zone_high=10.2,
                new_stop_loss=9.5,
                new_position_pct=10.0,
            )
        ]
        with (
            patch.object(cal, "redis_lock", _lock()),
            patch.object(cal, "_run_llm", AsyncMock(return_value=_content(items))),
        ):
            summary = await cal.run_calibration(
                session, _agent("active"), _DATE, "1020", quotes={}
            )
        assert summary["rejected"] == 1
        row = session.add.call_args.args[0]
        assert "未知标的代码" in row.reject_reason

    async def test_duplicate_code_second_rejected(self) -> None:
        plan = _plan()
        session = _session(scalar_values=[0], plans=[plan])
        items = [
            _item(action="adjust", new_stop_loss=9.3),
            _item(action="cancel"),
        ]
        with (
            patch.object(cal, "redis_lock", _lock()),
            patch.object(cal, "_run_llm", AsyncMock(return_value=_content(items))),
        ):
            summary = await cal.run_calibration(
                session, _agent("active"), _DATE, "1020", quotes={}
            )
        assert summary["applied"] == 1
        assert summary["rejected"] == 1
        rows = [call.args[0] for call in session.add.call_args_list]
        assert [row.status for row in rows] == ["applied", "rejected"]

    async def test_amendment_for_missing_plan_rejected(self) -> None:
        session = _session(scalar_values=[0], plans=[_plan(stock_code="600000")])
        items = [_item(action="cancel", stock_code="000001")]
        with (
            patch.object(cal, "redis_lock", _lock()),
            patch.object(cal, "_run_llm", AsyncMock(return_value=_content(items))),
        ):
            summary = await cal.run_calibration(
                session, _agent("active"), _DATE, "1020", quotes={}
            )
        assert summary["rejected"] == 1
        row = session.add.call_args.args[0]
        assert "未找到当日活跃计划" in row.reject_reason


@pytest.mark.unit
class TestValidateAdjust:
    def test_sell_target_inversion_rejected(self) -> None:
        plan = _plan(plan_type="sell", buy_zone_low=None, buy_zone_high=None)
        item = _item(action="adjust", new_target_price=9.0)
        reason = cal._validate_adjust(plan, item, price=10.0)
        assert reason is not None
        assert "止盈不高于止损" in reason

    def test_buy_zone_inversion_rejected(self) -> None:
        plan = _plan()
        item = _item(action="adjust", new_buy_zone_low=10.5, new_buy_zone_high=10.0)
        assert "倒挂" in (cal._validate_adjust(plan, item, price=None) or "")

    def test_stop_above_zone_low_rejected(self) -> None:
        plan = _plan()
        item = _item(action="adjust", new_stop_loss=9.9)
        assert "止损不低于买点区间下沿" in (cal._validate_adjust(plan, item, price=None) or "")

    def test_buy_missing_zone_rejected(self) -> None:
        plan = _plan(buy_zone_low=None, buy_zone_high=None)
        item = _item(action="adjust", new_stop_loss=9.0)
        assert "缺买点区间" in (cal._validate_adjust(plan, item, price=None) or "")

    def test_reasonable_adjust_passes_without_price(self) -> None:
        plan = _plan()
        item = _item(action="adjust", new_target_price=10.8)
        assert cal._validate_adjust(plan, item, price=None) is None


@pytest.mark.unit
class TestValidateAdd:
    async def test_sell_needs_stop_only(self) -> None:
        session = _session(scalar_values=["600000"])
        item = _item(
            action="add",
            plan_type="sell",
            new_stop_loss=9.0,
            new_target_price=11.0,
            new_position_pct=10.0,
        )
        assert await cal._validate_add(session, _agent(), item, price=None) is None

    async def test_missing_position_rejected(self) -> None:
        session = _session()
        item = _item(action="add", plan_type="buy", new_stop_loss=9.0, new_position_pct=None)
        reason = await cal._validate_add(session, _agent(), item, price=None)
        assert reason is not None
        assert "缺仓位" in reason

    async def test_missing_stop_rejected(self) -> None:
        session = _session()
        item = _item(action="add", plan_type="buy", new_position_pct=10.0)
        reason = await cal._validate_add(session, _agent(), item, price=None)
        assert reason is not None
        assert "缺止损" in reason
