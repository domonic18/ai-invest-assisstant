"""盘中执行观测查询服务测试（批次 8 PR-3：执行动态数据面）。

session 以 MagicMock + AsyncMock 替身（JSONB 模型无法在 sqlite 建表），
钉死契约：JSONB 逐键安全解析（缺键 None）、summary 恒全天口径不受
significant 过滤影响、缺省日期解析链（最近有观测日 → 当日兜底）、
尾盘行 plan_id 空容忍、agent 不存在 404。
"""

from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import NotFoundError
from app.models.paper_trade import PaperTradeExecObservation
from app.services.trading import (
    agent_exec_observation_service as svc,
)
from app.services.trading import agent_registry

pytestmark = pytest.mark.unit


def _obs(**overrides: Any) -> PaperTradeExecObservation:
    row = PaperTradeExecObservation(
        id=1,
        tick_time=datetime(2026, 9, 29, 1, 30, tzinfo=timezone.utc),
        trade_date=date(2026, 9, 29),
        agent_key="short-line",
        plan_id=11,
        stock_code="600000",
        market_snapshot={"price": 10.0, "prev_close": 9.9, "change_pct": 1.01},
        l0_verdict="triggered",
        trigger_reason="buy_zone",
        decision_answers={
            "served_model": "openjev-0.1",
            "thresholds": {"observe": 0.6, "fund_action": 0.85},
            "action": {"type": "choice", "choice": "立即执行", "confidence": 0.52},
            # openjev wire 真实形状：noul 存 p(yes)，score 是 0-4 加权位置
            "noul": {"type": "noul", "noul": 0.62},
            "score": {
                "type": "score",
                "score": 2.0,
                "probabilities": {"0": 0.1, "1": 0.2, "2": 0.4, "3": 0.2, "4": 0.1},
                "confidence": 0.4,
                "legend": {
                    "0": "1 大盘恐慌杀跌，不宜任何新动作",
                    "1": "2 大盘弱势，仅支持明确的止损离场",
                    "2": "3 大盘中性震荡，可中性执行",
                    "3": "4 大盘强势，支持顺势执行",
                    "4": "5 大盘极强且主线共振，可积极执行",
                },
            },
        },
        action="suppress",
        suppression_reason="below_threshold",
        is_shadow=True,
    )
    for key, value in overrides.items():
        setattr(row, key, value)
    return row


def _session(
    *,
    total: int = 1,
    rows: list[Any] | None = None,
    names: list[Any] | None = None,
    plans: list[Any] | None = None,
    summary: list[Any] | None = None,
) -> MagicMock:
    """list_agent_observations 的查询替身（显式 trade_date 路径：3 次 execute）。"""
    session = MagicMock()
    session.scalar = AsyncMock(return_value=total)
    session.scalars = AsyncMock(return_value=list(rows or []))
    results = []
    if rows:  # 无条目时名称/plan 回填查询被跳过，execute 直接消费 summary
        for payload in (names or [], plans or []):
            result = MagicMock()
            result.all.return_value = payload
            results.append(result)
    summary_result = MagicMock()
    summary_result.all.return_value = summary or []
    results.append(summary_result)
    session.execute = AsyncMock(side_effect=results)
    return session


@pytest.fixture(autouse=True)
def _known_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        agent_registry, "get_agent", AsyncMock(return_value=MagicMock(agent_key="short-line"))
    )


@pytest.mark.asyncio
class TestListAgentObservations:
    async def test_full_jsonb_parse(self) -> None:
        session = _session(
            rows=[_obs()],
            names=[("600000", "浦发银行")],
            plans=[(11, "buy")],
            summary=[("triggered", "suppress", "below_threshold", 1)],
        )
        page = await svc.list_agent_observations(
            session, "short-line", trade_date=date(2026, 9, 29), page=1, page_size=20
        )
        item = page.items[0]
        assert item.stock_name == "浦发银行"
        assert item.plan_type == "buy"
        assert item.price == 10.0
        assert item.change_pct == pytest.approx(1.01)
        assert item.action == "suppress"
        assert item.suppression_reason == "below_threshold"
        assert item.decision is not None
        assert item.decision.served_model == "openjev-0.1"
        assert item.decision.choice == "立即执行"
        assert item.decision.confidence == pytest.approx(0.52)
        assert item.decision.noul is True
        assert item.decision.score == 3.0
        assert item.decision.window is None
        assert page.trade_date == date(2026, 9, 29)
        assert page.total == 1

    async def test_answer_normalization_boundaries(self) -> None:
        """noul p(yes) 按 0.5 阈值归 boolean（真值化会让 p=0.06 成 True）；
        score 0-4 加权位置归一为 legend 口径 1-5。"""
        rows = [
            _obs(
                id=21,
                plan_id=11,
                decision_answers={
                    "served_model": "openjev-0.1",
                    "noul": {"type": "noul", "noul": 0.06},
                    "score": {"type": "score", "score": 0.0, "legend": {"0": "1 极弱"}},
                },
            ),
            _obs(
                id=22,
                plan_id=12,
                decision_answers={
                    "served_model": "openjev-0.1",
                    "noul": {"type": "noul", "noul": 0.5},
                    "score": {"type": "score", "score": 4.0, "legend": {"4": "5 极强"}},
                },
            ),
        ]
        session = _session(
            rows=rows,
            names=[("600000", "浦发银行")],
            plans=[(11, "sell"), (12, "sell")],
            summary=[("triggered", None, None, 2)],
        )
        page = await svc.list_agent_observations(
            session, "short-line", trade_date=date(2026, 9, 29), page=1, page_size=20
        )
        low, high = page.items
        assert low.decision is not None and high.decision is not None
        assert low.decision.noul is False  # p=0.06 明确「不支持」
        assert low.decision.score == pytest.approx(1.0)
        assert high.decision.noul is True  # 0.5 阈值含边界
        assert high.decision.score == pytest.approx(5.0)  # 满位可达「极强」

    async def test_no_action_row_without_answers(self) -> None:
        session = _session(
            total=0,
            rows=[],
            summary=[("no_action", None, None, 1)],
        )
        page = await svc.list_agent_observations(
            session, "short-line", trade_date=date(2026, 9, 29), page=1, page_size=20
        )
        # 显著过滤下无条目，但 summary 仍全天口径计入
        assert page.items == []
        assert page.summary.total_ticks == 1
        assert page.summary.significant_ticks == 0
        assert page.summary.l0_verdict_counts == {"no_action": 1}

    async def test_summary_full_day_scope(self) -> None:
        session = _session(
            rows=[_obs()],
            names=[("600000", "浦发银行")],
            plans=[(11, "buy")],
            summary=[
                ("triggered", "suppress", "below_threshold", 2),
                ("no_action", None, None, 5),
            ],
        )
        page = await svc.list_agent_observations(
            session, "short-line", trade_date=date(2026, 9, 29), page=1, page_size=20
        )
        # items 是显著过滤后的分页（1 条），summary 恒全天口径（7 tick）
        assert page.total == 1
        assert page.summary.total_ticks == 7
        assert page.summary.significant_ticks == 2
        assert page.summary.l0_verdict_counts == {"triggered": 2, "no_action": 5}
        assert page.summary.action_counts == {"suppress": 2}
        assert page.summary.suppression_counts == {"below_threshold": 2}

    async def test_tail_check_row_without_plan(self) -> None:
        row = _obs(
            id=9,
            plan_id=None,
            market_snapshot={
                "price": 9.4,
                "prev_close": 9.52,
                "change_pct": -1.26,
                "stop_loss": 9.5,
                "window": "tail_check",
            },
            l0_verdict="triggered",
            trigger_reason="stop_loss",
            decision_answers=None,
            action="suppress",
            suppression_reason="shadow_mode",
        )
        session = _session(
            rows=[row],
            names=[("600000", "浦发银行")],
            summary=[("triggered", "suppress", "shadow_mode", 1)],
        )
        page = await svc.list_agent_observations(
            session, "short-line", trade_date=date(2026, 9, 29), page=1, page_size=20
        )
        item = page.items[0]
        assert item.plan_id is None
        assert item.plan_type is None
        assert item.decision is None
        assert item.stock_name == "浦发银行"
        assert item.trigger_reason == "stop_loss"

    async def test_executed_row_order_fields(self) -> None:
        row = _obs(
            market_snapshot={
                "price": 10.0,
                "prev_close": 9.9,
                "change_pct": 1.01,
                "l0_detail": "触及买点区间",
                "cl_ord_id": "CL-1",
                "volume": 300,
            },
            action="execute",
            suppression_reason=None,
        )
        session = _session(
            rows=[row],
            names=[("600000", "浦发银行")],
            plans=[(11, "buy")],
            summary=[("triggered", "execute", None, 1)],
        )
        page = await svc.list_agent_observations(
            session, "short-line", trade_date=date(2026, 9, 29), page=1, page_size=20
        )
        item = page.items[0]
        assert item.cl_ord_id == "CL-1"
        assert item.order_volume == 300
        assert item.action == "execute"
        assert item.suppression_reason is None
        assert item.l0_detail == "触及买点区间"

    async def test_missing_jsonb_keys_tolerated(self) -> None:
        row = _obs(market_snapshot={}, decision_answers={})
        session = _session(
            rows=[row],
            names=[("600000", "浦发银行")],
            summary=[("triggered", "suppress", "below_threshold", 1)],
        )
        page = await svc.list_agent_observations(
            session, "short-line", trade_date=date(2026, 9, 29), page=1, page_size=20
        )
        item = page.items[0]
        assert item.price is None
        assert item.change_pct is None
        assert item.decision is None
        assert item.order_volume is None
        assert item.l0_detail is None

    async def test_agent_not_found_404(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            agent_registry, "get_agent", AsyncMock(side_effect=NotFoundError("不存在"))
        )
        session = _session()
        with pytest.raises(NotFoundError):
            await svc.list_agent_observations(
                session, "ghost", trade_date=date(2026, 9, 29), page=1, page_size=20
            )


@pytest.mark.asyncio
class TestDateResolveChain:
    async def test_falls_back_to_latest_observed_date(self) -> None:
        session = _session(
            rows=[_obs()],
            names=[("600000", "浦发银行")],
            summary=[("triggered", "suppress", "below_threshold", 1)],
        )
        resolve_result = MagicMock()
        resolve_result.scalar_one_or_none.return_value = date(2026, 9, 25)
        session.execute = AsyncMock(
            side_effect=[resolve_result, *session.execute.side_effect]
        )
        page = await svc.list_agent_observations(
            session, "short-line", trade_date=None, page=1, page_size=20
        )
        assert page.trade_date == date(2026, 9, 25)

    async def test_no_observations_falls_back_to_today(self) -> None:
        from app.core.clock import today_cn

        session = _session(rows=[], summary=[])
        resolve_result = MagicMock()
        resolve_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(side_effect=[resolve_result, *session.execute.side_effect])
        page = await svc.list_agent_observations(
            session, "short-line", trade_date=None, page=1, page_size=20
        )
        assert page.trade_date == today_cn()
