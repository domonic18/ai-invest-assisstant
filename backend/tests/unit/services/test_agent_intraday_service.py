"""盘中自主执行链服务测试（批次 8 PR-1）。

覆盖：L0 比价边界（买点区间/涨跌停触板/止损纪律否决/卖出止盈止损）、
L2 阈值分档与抑制原因、run_tick shadow 全链路留痕绝不下单、
判断模型异常 advisory 降级、active 真实下单推进状态机、
run_tail_check 状态短路幂等与持仓止损强检、plan_stock_codes。
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.decision_model.contracts import (
    DEFAULT_THRESHOLDS,
    JudgeChoiceAnswer,
    JudgeResponse,
    JudgeUsage,
)
from app.core.decision_model.errors import DecisionModelError
from app.services.trading import agent_intraday_service as svc
from app.services.trading.agent_intraday_questions import (
    CHOICE_ACTION_ABANDON,
    CHOICE_ACTION_EXECUTE,
    CHOICE_ACTION_WAIT,
)
from app.services.trading.agent_trade_service import RiskRejectedError
from app.services.trading.errors import AgentAccountNotDesignatedError

_DATE = date(2026, 9, 29)
_NOW = datetime(2026, 9, 29, 2, 0, tzinfo=timezone.utc)
THRESHOLDS = DEFAULT_THRESHOLDS


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
        "selection_id": None,
        "basis": "b",
        "triggered_cl_ord_id": None,
        "triggered_at": None,
        "raw": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _quote(price: float, prev_close: float = 10.0, name: str = "浦发银行") -> dict:
    return {
        "price": price,
        "prev_close": prev_close,
        "change_pct": round((price - prev_close) / prev_close * 100, 2),
        "name": name,
    }


def _agent(mode: str = "shadow") -> SimpleNamespace:
    return SimpleNamespace(agent_key="short-line", intraday_exec_mode=mode)


def _choice(plan_id: int, picked: str, confidence: float) -> JudgeChoiceAnswer:
    return JudgeChoiceAnswer(
        type="choice", choice=picked, probabilities={picked: confidence}, confidence=confidence
    )


def _response(answers: dict) -> JudgeResponse:
    return JudgeResponse(
        model="jev-test",
        answers=answers,
        usage=JudgeUsage(input_tokens=10, output_tokens=5, cost=None),
        request_id=None,
        latency_ms=1,
        config_id=None,
    )


def _session(
    scalars_result: list | None = None,
    rowcount: int = 1,
    plan_dates: list[tuple[str, date]] | None = None,
) -> MagicMock:
    """Mock 会话：execute 兼顾两种消费——生效计划日期查询（rows.all()）
    与计划状态推进 UPDATE（rowcount）。"""
    session = MagicMock()
    session.scalars = AsyncMock(return_value=scalars_result or [])
    exec_result = MagicMock(rowcount=rowcount)
    exec_result.all.return_value = (
        plan_dates if plan_dates is not None else [("short-line", _DATE)]
    )
    session.execute = AsyncMock(return_value=exec_result)
    session.add = MagicMock()
    session.commit = AsyncMock()
    return session


def _observations(session: MagicMock) -> list:
    return [call.args[0] for call in session.add.call_args_list]


@pytest.mark.unit
class TestEvaluateL0:
    def test_buy_in_zone_triggered(self) -> None:
        result = svc.evaluate_l0(_plan(), price=10.0, prev_close=10.0)
        assert result.verdict == svc.L0_TRIGGERED
        assert result.trigger_reason == svc.REASON_BUY_ZONE

    def test_buy_zone_boundaries_inclusive(self) -> None:
        assert svc.evaluate_l0(_plan(), price=9.80, prev_close=10.0).verdict == svc.L0_TRIGGERED
        assert svc.evaluate_l0(_plan(), price=10.20, prev_close=10.0).verdict == svc.L0_TRIGGERED

    def test_buy_below_zone_near_trigger(self) -> None:
        result = svc.evaluate_l0(_plan(), price=9.60, prev_close=10.0)
        assert result.verdict == svc.L0_NEAR_TRIGGER

    def test_buy_above_zone_no_chase(self) -> None:
        result = svc.evaluate_l0(_plan(), price=10.50, prev_close=10.0)
        assert result.verdict == svc.L0_NO_ACTION
        assert not result.reject

    def test_buy_below_stop_discipline_reject(self) -> None:
        result = svc.evaluate_l0(_plan(), price=9.40, prev_close=10.0)
        assert result.verdict == svc.L0_NO_ACTION
        assert result.reject

    def test_buy_missing_zone_reject(self) -> None:
        result = svc.evaluate_l0(_plan(buy_zone_low=None, buy_zone_high=None), price=10.0, prev_close=10.0)
        assert result.verdict == svc.L0_NO_ACTION
        assert result.reject

    def test_buy_at_limit_up_not_chased(self) -> None:
        """买点区间内触板涨停按不可成交处理（昨收 9.25 → 10% 板 10.175）。"""
        result = svc.evaluate_l0(_plan(), price=10.20, prev_close=9.25)
        assert result.verdict == svc.L0_NO_ACTION
        assert not result.reject

    def test_buy_below_limit_up_triggered(self) -> None:
        """区间内但未触板（昨收 9.30 → 板价 10.23）正常触发。"""
        assert svc.evaluate_l0(_plan(), price=10.20, prev_close=9.30).verdict == svc.L0_TRIGGERED

    def test_st_limit_band_uses_5pct(self) -> None:
        """ST 5% 板：昨收 9.6 → 板价 10.08，10.10 触板不追；非 ST 同价正常触发。"""
        result = svc.evaluate_l0(_plan(), price=10.10, prev_close=9.60, stock_name="ST 星源")
        assert result.verdict == svc.L0_NO_ACTION
        assert svc.evaluate_l0(_plan(), price=10.10, prev_close=9.60).verdict == svc.L0_TRIGGERED

    def test_buy_without_prev_close_skips_limit_check(self) -> None:
        assert svc.evaluate_l0(_plan(), price=10.0, prev_close=None).verdict == svc.L0_TRIGGERED

    def test_sell_target_triggered(self) -> None:
        plan = _plan(plan_type="sell")
        result = svc.evaluate_l0(plan, price=11.0, prev_close=10.0)
        assert result.verdict == svc.L0_TRIGGERED
        assert result.trigger_reason == svc.REASON_TARGET

    def test_sell_stop_loss_triggered(self) -> None:
        plan = _plan(plan_type="sell")
        result = svc.evaluate_l0(plan, price=9.50, prev_close=10.0)
        assert result.verdict == svc.L0_TRIGGERED
        assert result.trigger_reason == svc.REASON_STOP_LOSS

    def test_sell_between_no_action(self) -> None:
        plan = _plan(plan_type="sell")
        assert svc.evaluate_l0(plan, price=10.0, prev_close=10.0).verdict == svc.L0_NO_ACTION


@pytest.mark.unit
class TestDecide:
    def test_execute_at_fund_action(self) -> None:
        l0 = svc.L0Result(svc.L0_TRIGGERED, svc.REASON_BUY_ZONE)
        assert svc._decide(
            l0, (CHOICE_ACTION_EXECUTE, THRESHOLDS.fund_action), THRESHOLDS, plan_type="buy"
        ) == (
            svc.ACTION_EXECUTE,
            None,
        )

    def test_execute_below_fund_action_waits(self) -> None:
        l0 = svc.L0Result(svc.L0_TRIGGERED, svc.REASON_BUY_ZONE)
        assert svc._decide(
            l0, (CHOICE_ACTION_EXECUTE, 0.70), THRESHOLDS, plan_type="buy"
        ) == (svc.ACTION_WAIT, None)

    def test_execute_below_observe_suppressed(self) -> None:
        l0 = svc.L0Result(svc.L0_TRIGGERED, svc.REASON_BUY_ZONE)
        action, suppression = svc._decide(
            l0, (CHOICE_ACTION_EXECUTE, 0.50), THRESHOLDS, plan_type="buy"
        )
        assert (action, suppression) == (svc.ACTION_SUPPRESS, svc.SUPPRESS_BELOW_THRESHOLD)

    def test_wait_choice(self) -> None:
        l0 = svc.L0Result(svc.L0_TRIGGERED, svc.REASON_BUY_ZONE)
        assert svc._decide(l0, (CHOICE_ACTION_WAIT, 0.90), THRESHOLDS, plan_type="buy") == (
            svc.ACTION_WAIT,
            None,
        )

    def test_wait_choice_low_confidence_suppressed(self) -> None:
        l0 = svc.L0Result(svc.L0_TRIGGERED, svc.REASON_BUY_ZONE)
        action, suppression = svc._decide(
            l0, (CHOICE_ACTION_WAIT, 0.30), THRESHOLDS, plan_type="buy"
        )
        assert (action, suppression) == (svc.ACTION_SUPPRESS, svc.SUPPRESS_BELOW_THRESHOLD)

    def test_abandon_choice(self) -> None:
        l0 = svc.L0Result(svc.L0_TRIGGERED, svc.REASON_BUY_ZONE)
        assert svc._decide(
            l0, (CHOICE_ACTION_ABANDON, 0.90), THRESHOLDS, plan_type="buy"
        ) == (
            svc.ACTION_ABANDON,
            None,
        )

    def test_missing_choice_is_model_degraded(self) -> None:
        l0 = svc.L0Result(svc.L0_TRIGGERED, svc.REASON_BUY_ZONE)
        action, suppression = svc._decide(l0, None, THRESHOLDS, plan_type="buy")
        assert (action, suppression) == (svc.ACTION_SUPPRESS, svc.SUPPRESS_MODEL_DEGRADED)

    def test_near_trigger_waits_regardless_of_choice(self) -> None:
        l0 = svc.L0Result(svc.L0_NEAR_TRIGGER)
        assert svc._decide(
            l0, (CHOICE_ACTION_EXECUTE, 0.99), THRESHOLDS, plan_type="buy"
        ) == (
            svc.ACTION_WAIT,
            None,
        )

    def test_l0_reject_suppressed(self) -> None:
        l0 = svc.L0Result(svc.L0_NO_ACTION, reject=True)
        assert svc._decide(l0, None, THRESHOLDS, plan_type="buy") == (
            svc.ACTION_SUPPRESS,
            svc.SUPPRESS_L0_REJECT,
        )

    def test_plain_no_action_has_no_decision(self) -> None:
        assert svc._decide(svc.L0Result(svc.L0_NO_ACTION), None, THRESHOLDS, plan_type="buy") == (
            None,
            None,
        )

    def test_sell_execute_at_exit_action_gate(self) -> None:
        """卖出离场 execute 闸门降档：0.6-0.85 区间即执行（开仓仍要求 fund_action）。"""
        for reason in (svc.REASON_STOP_LOSS, svc.REASON_TARGET):
            l0 = svc.L0Result(svc.L0_TRIGGERED, reason)
            assert svc._decide(
                l0, (CHOICE_ACTION_EXECUTE, 0.70), THRESHOLDS, plan_type="sell"
            ) == (svc.ACTION_EXECUTE, None)

    def test_sell_execute_boundary_inclusive(self) -> None:
        l0 = svc.L0Result(svc.L0_TRIGGERED, svc.REASON_STOP_LOSS)
        assert svc._decide(
            l0, (CHOICE_ACTION_EXECUTE, THRESHOLDS.exit_action), THRESHOLDS, plan_type="sell"
        ) == (svc.ACTION_EXECUTE, None)

    def test_sell_execute_below_exit_gate_suppressed(self) -> None:
        l0 = svc.L0Result(svc.L0_TRIGGERED, svc.REASON_STOP_LOSS)
        action, suppression = svc._decide(
            l0, (CHOICE_ACTION_EXECUTE, 0.59), THRESHOLDS, plan_type="sell"
        )
        assert (action, suppression) == (svc.ACTION_SUPPRESS, svc.SUPPRESS_BELOW_THRESHOLD)

    def test_buy_in_exit_band_still_waits(self) -> None:
        """0.6-0.85 区间对买入仍是 wait（分档只放宽离场）。"""
        l0 = svc.L0Result(svc.L0_TRIGGERED, svc.REASON_BUY_ZONE)
        assert svc._decide(
            l0, (CHOICE_ACTION_EXECUTE, 0.70), THRESHOLDS, plan_type="buy"
        ) == (svc.ACTION_WAIT, None)


@pytest.mark.unit
class TestQuestionAssembly:
    """state 计划上下文与动作题面方向分变体（判断模型不再盲答）。"""

    def test_state_sell_plan_context(self) -> None:
        plan = _plan(id=7, plan_type="sell")
        l0 = svc.L0Result(svc.L0_TRIGGERED, svc.REASON_STOP_LOSS)
        state = svc._state(
            trade_date=_DATE,
            quotes={"600000": _quote(9.40)},
            index_snapshot={"code": "000001"},
            candidates=[(plan, _quote(9.40), l0)],
        )
        entry = state["plans"]["7"]
        assert entry["stock_code"] == "600000"
        assert entry["direction"] == "卖出"
        assert entry["trigger"] == "击穿止损线"
        assert entry["levels"] == {"stop_loss": 9.5, "target_price": 11.0}
        assert entry["price"] == 9.40
        assert state["index"] == {"code": "000001"}

    def test_state_buy_plan_context(self) -> None:
        plan = _plan(id=1)
        l0 = svc.L0Result(svc.L0_TRIGGERED, svc.REASON_BUY_ZONE)
        state = svc._state(
            trade_date=_DATE,
            quotes={"600000": _quote(10.0)},
            index_snapshot=None,
            candidates=[(plan, _quote(10.0), l0)],
        )
        entry = state["plans"]["1"]
        assert entry["direction"] == "买入"
        assert entry["trigger"] == "进入买点区间"
        assert entry["levels"] == {
            "stop_loss": 9.5,
            "buy_zone_low": 9.8,
            "buy_zone_high": 10.2,
        }

    def test_action_question_split_by_direction(self) -> None:
        buy = _plan(id=1, plan_type="buy")
        sell = _plan(id=2, plan_type="sell")
        questions = svc._questions(
            [
                (buy, _quote(10.0), svc.L0Result(svc.L0_TRIGGERED, svc.REASON_BUY_ZONE)),
                (sell, _quote(9.40), svc.L0Result(svc.L0_TRIGGERED, svc.REASON_STOP_LOSS)),
            ]
        )
        assert questions["1:action"] is svc.CHOICE_INTRADAY_ACTION_BUY
        assert questions["2:action"] is svc.CHOICE_INTRADAY_ACTION_SELL
        # sell 放弃选项收敛为"非有效跌破"语义，不再泛化"破位即放弃"
        assert "保留仓位" in questions["2:action"].criteria[CHOICE_ACTION_ABANDON]
        assert "卖出离场" in questions["2:action"].criteria[CHOICE_ACTION_EXECUTE]
        # 分时题沿用既有方向拆分，大盘题共用
        assert questions["1:noul"] is svc.NOUL_BUY_TIMING
        assert questions["2:noul"] is svc.NOUL_EXIT_TIMING
        assert questions["1:score"] is questions["2:score"] is svc.SCORE_MARKET_SUPPORT

    async def test_run_tick_passes_plan_state_to_model(self) -> None:
        """run_tick 组装的 state 含触发计划上下文（接线防回归）。"""
        plans = [_plan(id=1, plan_type="sell")]
        session = _session(scalars_result=plans)
        with (
            patch.object(
                svc.agent_registry, "get_active_agents", new=AsyncMock(return_value=[_agent("shadow")])
            ),
            patch.object(svc, "ask_decision", AsyncMock(return_value=_response({}))) as ask_mock,
            patch.object(
                svc.account_service, "resolve_agent_account", AsyncMock(return_value=SimpleNamespace())
            ),
            patch.object(svc, "execute_agent_order", AsyncMock()),
        ):
            await svc.run_tick(
                session, trade_date=_DATE, now=_NOW, quotes={"600000": _quote(9.40)}
            )
        state = ask_mock.await_args.kwargs["state"]
        assert state["plans"]["1"]["direction"] == "卖出"
        assert state["plans"]["1"]["trigger"] == "击穿止损线"


@pytest.mark.unit
class TestRunTick:
    async def _run(
        self,
        session: MagicMock,
        agent: SimpleNamespace,
        plans: list,
        quotes: dict,
        answers: dict | None = None,
        ask_error: Exception | None = None,
    ) -> tuple[dict[str, int], AsyncMock]:
        """shadow 语义 run_tick：判断/账户/下单全部 mock，返回 (counters, order_mock)。"""
        with (
            patch.object(
                svc.agent_registry, "get_active_agents", new=AsyncMock(return_value=[agent])
            ),
            patch.object(
                svc,
                "ask_decision",
                AsyncMock(side_effect=ask_error, return_value=_response(answers or {})),
            ),
            patch.object(
                svc.account_service,
                "resolve_agent_account",
                AsyncMock(return_value=SimpleNamespace()),
            ),
            patch.object(svc, "execute_agent_order", AsyncMock()) as order_mock,
        ):
            counters = await svc.run_tick(
                session, trade_date=_DATE, now=_NOW, quotes=quotes, recorders={}
            )
        return counters, order_mock

    async def test_shadow_full_chain_no_order(self) -> None:
        """shadow 触发计划只落观测，绝不下单（execute_agent_order 未调用）。"""
        plans = [
            _plan(id=1, stock_code="600000"),
            _plan(id=2, stock_code="000001"),
            _plan(id=3, stock_code="300001"),
        ]
        quotes = {
            "600000": _quote(10.0),
            "000001": _quote(9.60),
            "300001": _quote(10.50),
        }
        answers = {"1:action": _choice(1, CHOICE_ACTION_EXECUTE, 0.90)}
        session = _session(scalars_result=plans)
        counters, order_mock = await self._run(session, _agent("shadow"), plans, quotes, answers)
        order_mock.assert_not_called()
        assert counters["evaluated"] == 3
        assert counters["candidates"] == 1
        assert counters["shadow_executed"] == 1
        assert counters["executed"] == 0

        rows = {row.stock_code: row for row in _observations(session)}
        assert rows["600000"].action == svc.ACTION_EXECUTE
        assert rows["600000"].suppression_reason == svc.SUPPRESS_SHADOW
        assert rows["600000"].is_shadow is True
        assert rows["600000"].l0_verdict == svc.L0_TRIGGERED
        assert rows["600000"].trigger_reason == svc.REASON_BUY_ZONE
        assert rows["000001"].action == svc.ACTION_WAIT
        assert rows["000001"].l0_verdict == svc.L0_NEAR_TRIGGER
        assert rows["300001"].action is None
        assert rows["300001"].l0_verdict == svc.L0_NO_ACTION
        session.commit.assert_awaited_once()

    async def test_model_error_degrades_to_pure_l0(self) -> None:
        """判断模型异常 advisory 降级：触发计划记 model_degraded，不用阈值近似。"""
        plans = [_plan(id=1)]
        session = _session(scalars_result=plans)
        counters, order_mock = await self._run(
            session,
            _agent("shadow"),
            plans,
            {"600000": _quote(10.0)},
            ask_error=DecisionModelError("boom"),
        )
        order_mock.assert_not_called()
        assert counters["degraded"] == 1
        row = _observations(session)[0]
        assert row.l0_verdict == svc.L0_DEGRADED
        assert row.action == svc.ACTION_SUPPRESS
        assert row.suppression_reason == svc.SUPPRESS_MODEL_DEGRADED

    async def test_active_orders_and_advances_plan(self) -> None:
        """active 模式触发即真实下单（context=scheduled）并推进计划状态机。"""
        plans = [_plan(id=1)]
        session = _session(scalars_result=plans)
        account = SimpleNamespace()
        order_result = {"cl_ord_id": "CL1"}
        with (
            patch.object(svc.agent_registry, "get_active_agents", new=AsyncMock(return_value=[_agent("active")])),
            patch.object(svc, "_effective_plan_dates", AsyncMock(return_value={"short-line": _DATE})),
            patch.object(svc, "ask_decision", AsyncMock(return_value=_response({"1:action": _choice(1, CHOICE_ACTION_EXECUTE, 0.90)}))),
            patch.object(svc.account_service, "resolve_agent_account", AsyncMock(return_value=account)),
            patch.object(svc, "_buy_volume", AsyncMock(return_value=100)),
            patch.object(svc, "execute_agent_order", AsyncMock(return_value=order_result)) as order_mock,
        ):
            counters = await svc.run_tick(
                session, trade_date=_DATE, now=_NOW, quotes={"600000": _quote(10.0)}
            )
        assert counters["executed"] == 1
        order_mock.assert_awaited_once()
        kwargs = order_mock.await_args.kwargs
        assert kwargs["symbol"] == "600000"
        assert kwargs["side"] == "buy"
        assert kwargs["volume"] == 100
        assert kwargs["context"] == "scheduled"
        assert kwargs["plan_id"] == 1
        assert kwargs["account"] is account
        session.execute.assert_awaited_once()  # 计划状态 UPDATE
        row = _observations(session)[0]
        assert row.is_shadow is False
        assert row.action == svc.ACTION_EXECUTE
        assert row.suppression_reason is None
        assert row.market_snapshot["cl_ord_id"] == "CL1"

    async def test_active_risk_rejected_suppressed(self) -> None:
        plans = [_plan(id=1)]
        session = _session(scalars_result=plans)
        with (
            patch.object(svc.agent_registry, "get_active_agents", new=AsyncMock(return_value=[_agent("active")])),
            patch.object(svc, "ask_decision", AsyncMock(return_value=_response({"1:action": _choice(1, CHOICE_ACTION_EXECUTE, 0.90)}))),
            patch.object(svc.account_service, "resolve_agent_account", AsyncMock(return_value=SimpleNamespace())),
            patch.object(svc, "_buy_volume", AsyncMock(return_value=100)),
            patch.object(svc, "execute_agent_order", AsyncMock(side_effect=RiskRejectedError("仓位超限"))),
        ):
            counters = await svc.run_tick(
                session, trade_date=_DATE, now=_NOW, quotes={"600000": _quote(10.0)}
            )
        assert counters["suppressed"] == 1
        row = _observations(session)[0]
        assert row.action == svc.ACTION_SUPPRESS
        assert row.suppression_reason == svc.SUPPRESS_RISK_REJECTED

    async def test_missing_quote_not_evaluated(self) -> None:
        session = _session(scalars_result=[_plan(id=1)])
        counters, _order_mock = await self._run(session, _agent("shadow"), [_plan(id=1)], {})
        assert counters["evaluated"] == 0
        assert counters["candidates"] == 0
        assert _observations(session) == []


@pytest.mark.unit
class TestRunTailCheck:
    async def test_shadow_tail_stop_observation(self) -> None:
        """尾盘强检跌破止损：shadow 落观测不下单；当日未触发计划批量置 expired。"""
        session = _session(scalars_result=[_plan(id=1, stop_loss=Decimal("9.50"))], rowcount=2)
        with (
            patch.object(svc.agent_registry, "get_active_agents", new=AsyncMock(return_value=[_agent("shadow")])),
            patch.object(svc.account_service, "resolve_agent_account", AsyncMock(return_value=SimpleNamespace())),
            patch.object(svc, "execute_agent_order", AsyncMock()) as order_mock,
        ):
            counters = await svc.run_tail_check(
                session,
                trade_date=_DATE,
                now=_NOW,
                quotes={"600000": _quote(9.40)},
                recorders={},
            )
            order_mock.assert_not_called()
        assert counters == {"expired": 2, "checked": 1, "triggered": 1, "executed": 0}
        row = _observations(session)[0]
        assert row.plan_id is None
        assert row.l0_verdict == svc.L0_TRIGGERED
        assert row.trigger_reason == svc.REASON_STOP_LOSS
        assert row.action == svc.ACTION_EXECUTE
        assert row.suppression_reason == svc.SUPPRESS_SHADOW
        assert row.market_snapshot["window"] == "tail_check"

    async def test_state_short_circuit_idempotent(self) -> None:
        """二次尾盘跑批已无 active 行：expired 计数归零（状态短路幂等）。"""
        session = _session(scalars_result=[], rowcount=0)

        def _dates_result() -> MagicMock:
            result = MagicMock()
            result.all.return_value = [("short-line", _DATE)]
            return result

        # 每轮 run_tail_check 两次 execute：生效日期查询 + 计划状态 UPDATE
        session.execute = AsyncMock(
            side_effect=[
                _dates_result(),
                MagicMock(rowcount=2),
                _dates_result(),
                MagicMock(rowcount=0),
            ]
        )
        with (
            patch.object(svc.agent_registry, "get_active_agents", new=AsyncMock(return_value=[_agent("shadow")])),
            patch.object(svc.account_service, "resolve_agent_account", AsyncMock(return_value=SimpleNamespace())),
        ):
            first = await svc.run_tail_check(session, trade_date=_DATE, now=_NOW, quotes={})
            second = await svc.run_tail_check(session, trade_date=_DATE, now=_NOW, quotes={})
        assert first["expired"] == 2
        assert second["expired"] == 0

    async def test_active_tail_stop_sells_holding(self) -> None:
        session = _session(scalars_result=[_plan(id=1, stop_loss=Decimal("9.50"))], rowcount=1)
        with (
            patch.object(svc.agent_registry, "get_active_agents", new=AsyncMock(return_value=[_agent("active")])),
            patch.object(svc.account_service, "resolve_agent_account", AsyncMock(return_value=SimpleNamespace())),
            patch.object(svc, "_held_volume", AsyncMock(return_value=100)),
            patch.object(svc, "execute_agent_order", AsyncMock(return_value={"cl_ord_id": "CL9"})) as order_mock,
        ):
            counters = await svc.run_tail_check(
                session, trade_date=_DATE, now=_NOW, quotes={"600000": _quote(9.40)}
            )
        assert counters["executed"] == 1
        kwargs = order_mock.await_args.kwargs
        assert kwargs["side"] == "sell"
        assert kwargs["context"] == "scheduled"
        row = _observations(session)[0]
        assert row.is_shadow is False
        assert row.action == svc.ACTION_EXECUTE

    async def test_price_above_stop_skipped(self) -> None:
        session = _session(scalars_result=[_plan(id=1, stop_loss=Decimal("9.50"))], rowcount=1)
        with (
            patch.object(svc.agent_registry, "get_active_agents", new=AsyncMock(return_value=[_agent("shadow")])),
            patch.object(svc.account_service, "resolve_agent_account", AsyncMock(return_value=SimpleNamespace())),
        ):
            counters = await svc.run_tail_check(
                session, trade_date=_DATE, now=_NOW, quotes={"600000": _quote(10.0)}
            )
        assert counters["checked"] == 1
        assert counters["triggered"] == 0
        assert _observations(session) == []

    async def test_missing_account_skips_holdings_check(self) -> None:
        session = _session(scalars_result=[], rowcount=1)
        with (
            patch.object(svc.agent_registry, "get_active_agents", new=AsyncMock(return_value=[_agent("shadow")])),
            patch.object(
                svc.account_service,
                "resolve_agent_account",
                AsyncMock(side_effect=AgentAccountNotDesignatedError("no account")),
            ),
        ):
            counters = await svc.run_tail_check(session, trade_date=_DATE, now=_NOW, quotes={})
        assert counters == {"expired": 1, "checked": 0, "triggered": 0, "executed": 0}
        session.scalars.assert_not_awaited()


@pytest.mark.unit
class TestPlanStockCodes:
    async def test_dedupes_active_agents_plans(self) -> None:
        session = _session(scalars_result=["600000", "000001", "600000"])
        codes = await svc.plan_stock_codes(session, trade_date=_DATE)
        assert codes == {"600000", "000001"}

    async def test_no_effective_plan_set_returns_empty(self) -> None:
        session = _session(plan_dates=[])
        codes = await svc.plan_stock_codes(session, trade_date=_DATE)
        assert codes == set()
        session.scalars.assert_not_awaited()


@pytest.mark.unit
class TestHeldVolume:
    async def test_matches_counter_symbol_key(self) -> None:
        """柜台持仓行键为掘金 symbol（SZSE.000504），按裸代码匹配命中。"""
        client = SimpleNamespace(
            get_positions=AsyncMock(
                return_value=[
                    {"symbol": "SZSE.301311", "volume": 100},
                    {"symbol": "SZSE.000504", "volume": 100},
                    {"symbol": "SHSE.600815", "volume": 100},
                ]
            )
        )
        with (
            patch("app.services.trading.client.get_client", return_value=client),
            patch.object(svc.account_service, "credentials_for", return_value=object()),
        ):
            assert await svc._held_volume(MagicMock(), "000504") == 100
            assert await svc._held_volume(MagicMock(), "600815") == 100
            assert await svc._held_volume(MagicMock(), "002238") == 0

    async def test_empty_positions_return_zero(self) -> None:
        """柜台空持仓（{} 或 []）返回 0。"""
        client = SimpleNamespace(get_positions=AsyncMock(return_value={}))
        with (
            patch("app.services.trading.client.get_client", return_value=client),
            patch.object(svc.account_service, "credentials_for", return_value=object()),
        ):
            assert await svc._held_volume(MagicMock(), "000504") == 0


@pytest.mark.unit
class TestReconcilePendingOrders:
    async def test_triggers_sync_when_pending(self) -> None:
        """当日有未结 agent 委托 → 触发单账户即时同步回填成交终态。"""
        agent = SimpleNamespace(agent_key="short-line")
        account = SimpleNamespace(id=4)
        session = _session()
        session.scalar = AsyncMock(return_value=1)
        with (
            patch.object(svc, "_account_or_none", AsyncMock(return_value=account)),
            patch(
                "app.services.trading.paper_trade_sync.sync_account_now",
                new_callable=AsyncMock,
            ) as sync_mock,
        ):
            await svc._reconcile_pending_orders(session, agent)
        sync_mock.assert_awaited_once_with(session, account)

    async def test_skips_without_pending(self) -> None:
        """全部委托已终态 → 不触发同步（省锁与柜台往返）。"""
        session = _session()
        session.scalar = AsyncMock(return_value=0)
        with (
            patch.object(svc, "_account_or_none", AsyncMock(return_value=SimpleNamespace(id=4))),
            patch(
                "app.services.trading.paper_trade_sync.sync_account_now",
                new_callable=AsyncMock,
            ) as sync_mock,
        ):
            await svc._reconcile_pending_orders(session, SimpleNamespace(agent_key="short-line"))
        sync_mock.assert_not_awaited()

    async def test_skips_without_account(self) -> None:
        """未绑定账户 → 不查询不触发。"""
        session = _session()
        session.scalar = AsyncMock()
        with (
            patch.object(svc, "_account_or_none", AsyncMock(return_value=None)),
            patch(
                "app.services.trading.paper_trade_sync.sync_account_now",
                new_callable=AsyncMock,
            ) as sync_mock,
        ):
            await svc._reconcile_pending_orders(session, SimpleNamespace(agent_key="short-line"))
        sync_mock.assert_not_awaited()
        session.scalar.assert_not_awaited()

    async def test_sync_error_swallowed(self) -> None:
        """同步异常（含 16:00 批量同步锁冲突）不冒泡，下一拍重试。"""
        from app.core.exceptions import ConflictError

        session = _session()
        session.scalar = AsyncMock(return_value=1)
        with (
            patch.object(svc, "_account_or_none", AsyncMock(return_value=SimpleNamespace(id=4))),
            patch(
                "app.services.trading.paper_trade_sync.sync_account_now",
                new_callable=AsyncMock,
                side_effect=ConflictError("模拟盘同步正在执行，请稍后重试"),
            ),
        ):
            await svc._reconcile_pending_orders(session, SimpleNamespace(agent_key="short-line"))
