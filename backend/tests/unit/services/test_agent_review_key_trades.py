"""长周期关键交易确定性筛选测试（标签优先级 / 去重 / 截断 / 输入裁剪）。"""

from datetime import date
from decimal import Decimal

import pytest

from app.services.trading.agent_review_key_trades import (
    KEY_TRADE_MAX,
    KEY_TRADE_TOP_N,
    TAG_LOSER,
    TAG_OFF_PLAN,
    TAG_OUT_OF_ZONE,
    TAG_REJECTED,
    TAG_WINNER,
    KeyTradeSelection,
    filter_window_input,
    select_key_trades,
)
from app.services.trading.agent_review_metrics import (
    ExecutionRecord,
    PlanRecord,
    RealizedTrade,
)
from app.services.trading.paper_trade_converters import SIDE_BUY, SIDE_SELL

_DAY = date(2026, 7, 15)


def _execution(
    cl_ord_id: str | None,
    *,
    side: int = SIDE_BUY,
    price: str = "10",
    stock_code: str = "600000",
) -> ExecutionRecord:
    return ExecutionRecord(
        trade_date=_DAY,
        stock_code=stock_code,
        side=side,
        price=Decimal(price),
        volume=100,
        turnover=Decimal(price) * 100,
        commission=Decimal("1"),
        cl_ord_id=cl_ord_id,
    )


def _plan(plan_type: str = "buy", low: str = "9", high: str = "10.5") -> PlanRecord:
    return PlanRecord(
        plan_date=_DAY,
        stock_code="600000",
        plan_type=plan_type,
        buy_zone_low=Decimal(low),
        buy_zone_high=Decimal(high),
    )


def _trade(cl_ord_id: str, profit: str) -> RealizedTrade:
    return RealizedTrade(
        trade_date=_DAY,
        stock_code="600000",
        profit=Decimal(profit),
        cl_ord_id=cl_ord_id,
    )


@pytest.mark.unit
class TestSelectKeyTrades:
    def test_ranks_winners_and_losers_by_profit(self) -> None:
        realized = [
            _trade("W1", "300"),
            _trade("W2", "500"),
            _trade("L1", "-100"),
            _trade("L2", "-400"),
            _trade("W3", "100"),
            _trade("L3", "-50"),
        ]
        selection = select_key_trades(executions=[], plans=[], realized=realized)

        assert selection.cl_ord_ids[:KEY_TRADE_TOP_N] == ("W2", "W1", "W3")
        assert selection.tags["W2"] == (TAG_WINNER,)
        assert selection.tags["L2"] == (TAG_LOSER,)
        assert "L3" in selection.cl_ord_ids

    def test_ignores_trades_without_cl_ord_id(self) -> None:
        realized = [_trade("W1", "100")]
        realized.append(
            RealizedTrade(trade_date=_DAY, stock_code="600000", profit=Decimal("999"))
        )
        selection = select_key_trades(executions=[], plans=[], realized=realized)
        assert selection.cl_ord_ids == ("W1",)

    def test_tags_off_plan_and_out_of_zone(self) -> None:
        executions = [
            _execution("OFF", stock_code="000001"),
            _execution("ZONE", price="11"),
            _execution("IN", price="10"),
        ]
        selection = select_key_trades(
            executions=executions, plans=[_plan()], realized=[]
        )

        assert selection.tags["OFF"] == (TAG_OFF_PLAN,)
        assert selection.tags["ZONE"] == (TAG_OUT_OF_ZONE,)
        assert "IN" not in selection.tags

    def test_sell_without_plan_is_not_out_of_zone(self) -> None:
        plan_buy = _plan("buy", low="9", high="10.5")
        execution = _execution("S1", side=SIDE_SELL, price="20")
        selection = select_key_trades(
            executions=[execution], plans=[plan_buy], realized=[]
        )
        assert selection.tags["S1"] == (TAG_OFF_PLAN,)

    def test_merges_tags_for_same_order(self) -> None:
        """盈利卖出 + 计划外：同一 cl_ord_id 只出现一次，两个标签都保留。"""
        execution = _execution("X", side=SIDE_SELL, price="20")
        selection = select_key_trades(
            executions=[execution],
            plans=[],
            realized=[_trade("X", "200")],
        )
        assert selection.cl_ord_ids == ("X",)
        assert selection.tags["X"] == (TAG_WINNER, TAG_OFF_PLAN)

    def test_rejected_deduped_with_other_tags(self) -> None:
        """废单拒单与计划外/盈利标签合并，同一 cl_ord_id 只出现一次。"""
        selection = select_key_trades(
            executions=[
                _execution("X", stock_code="000001"),
                _execution("Y", price="11"),
            ],
            plans=[_plan()],
            realized=[],
            rejected_cl_ord_ids=["X", "Y", "R1", "R1"],
        )
        # X/Y 由执行偏差进入，R1 由拒单进入（重复拒单去重）
        assert selection.cl_ord_ids == ("X", "Y", "R1")
        assert selection.tags["X"] == (TAG_OFF_PLAN, TAG_REJECTED)
        assert selection.tags["Y"] == (TAG_OUT_OF_ZONE, TAG_REJECTED)
        assert selection.tags["R1"] == (TAG_REJECTED,)

    def test_caps_each_category_and_reports_candidates(self) -> None:
        executions = [
            _execution(f"E{index}", stock_code=f"60000{index}", price="99")
            for index in range(KEY_TRADE_MAX + 5)
        ]
        selection = select_key_trades(executions=executions, plans=[], realized=[])

        # 计划外单逐类限量，候选数仍报全量
        assert len(selection.cl_ord_ids) == KEY_TRADE_TOP_N
        assert selection.total_candidates == len(executions)
        assert set(selection.tags) == set(selection.cl_ord_ids)

    def test_rejected_survives_deviation_overflow(self) -> None:
        """计划外单溢出时拒单仍在结果内（需求 §4.2：废单必点评）。"""
        executions = [
            _execution(f"E{index}", stock_code=f"60000{index}", price="99")
            for index in range(KEY_TRADE_MAX + 5)
        ]
        selection = select_key_trades(
            executions=executions,
            plans=[],
            realized=[],
            rejected_cl_ord_ids=["R1", "R2"],
        )

        assert "R1" in selection.cl_ord_ids
        assert "R2" in selection.cl_ord_ids
        assert selection.tags["R1"] == (TAG_REJECTED,)
        assert len(selection.cl_ord_ids) <= KEY_TRADE_MAX

    def test_all_categories_fit_within_total_cap(self) -> None:
        """五类各自满载时总数不超过 KEY_TRADE_MAX（不会挤掉整类）。"""
        realized = [_trade(f"W{i}", "100") for i in range(KEY_TRADE_TOP_N * 2)]
        realized += [_trade(f"L{i}", "-100") for i in range(KEY_TRADE_TOP_N * 2)]
        executions = [
            _execution(f"OFF{i}", stock_code=f"00000{i}") for i in range(KEY_TRADE_TOP_N * 2)
        ] + [
            _execution(f"ZONE{i}", price="99") for i in range(KEY_TRADE_TOP_N * 2)
        ]
        selection = select_key_trades(
            executions=executions,
            plans=[_plan()],
            realized=realized,
            rejected_cl_ord_ids=[f"R{i}" for i in range(KEY_TRADE_TOP_N * 2)],
        )

        assert len(selection.cl_ord_ids) == KEY_TRADE_MAX
        assert any(TAG_REJECTED in tags for tags in selection.tags.values())

    def test_to_wire_is_json_ready(self) -> None:
        selection = KeyTradeSelection(
            cl_ord_ids=("A",), tags={"A": (TAG_WINNER,)}, total_candidates=5
        )
        wire = selection.to_wire()
        assert wire["cl_ord_ids"] == ["A"]
        assert wire["tags"] == {"A": [TAG_WINNER]}
        assert "不代表全部交易" in wire["note"]


@pytest.mark.unit
class TestFilterWindowInput:
    def test_filters_orders_executions_and_names(self) -> None:
        window_input = {
            "orders": [
                {"cl_ord_id": "A", "stock_code": "600000"},
                {"cl_ord_id": "B", "stock_code": "000001"},
            ],
            "executions": [
                {"cl_ord_id": "A", "symbol": "SHSE.600000"},
                {"cl_ord_id": "C", "symbol": "SZSE.000001"},
            ],
            "stock_names": {"600000": "浦发银行", "000001": "平安银行"},
            "nav": [{"date": "2026-07-15"}],
        }
        selection = KeyTradeSelection(
            cl_ord_ids=("A",), tags={"A": (TAG_WINNER,)}, total_candidates=3
        )
        result = filter_window_input(window_input, selection)

        assert [order["cl_ord_id"] for order in result["orders"]] == ["A"]
        assert [row["cl_ord_id"] for row in result["executions"]] == ["A"]
        assert result["stock_names"] == {"600000": "浦发银行"}
        assert result["nav"] == window_input["nav"]
        assert result["key_trades"]["cl_ord_ids"] == ["A"]
        # 不修改入参
        assert len(window_input["orders"]) == 2
        assert "key_trades" not in window_input

    def test_execution_only_order_prunes_to_bare_code(self) -> None:
        window_input = {
            "orders": [],
            "executions": [{"cl_ord_id": "C", "symbol": "SZSE.000001"}],
            "stock_names": {"600000": "浦发银行", "000001": "平安银行"},
        }
        selection = KeyTradeSelection(
            cl_ord_ids=("C",), tags={"C": (TAG_OFF_PLAN,)}, total_candidates=1
        )
        result = filter_window_input(window_input, selection)
        assert result["stock_names"] == {"000001": "平安银行"}
