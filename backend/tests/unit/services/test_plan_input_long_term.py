"""长线三支柱注入单测：weekly 触发/daily 不触发、无锚点剔除、财务降级、图谱与提醒合流。"""

from contextlib import ExitStack
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.trading import agent_plan_input

pytestmark = pytest.mark.unit

_TRADE_DATE = date(2026, 10, 16)


def _weekly_agent() -> SimpleNamespace:
    return SimpleNamespace(
        agent_key="long-line",
        llm_config_id=None,
        methodology_source_id=None,
        name="长线舵手",
        tagline="价值长线",
        plan_cadence="weekly",
    )


def _daily_agent() -> SimpleNamespace:
    return SimpleNamespace(
        agent_key="short-line",
        llm_config_id=None,
        methodology_source_id=None,
        name="短线猎手",
        tagline="趋势短线",
        plan_cadence="daily",
    )


def _collect_patches(
    pillars: dict | None = None,
    anchors: tuple[dict, list[str]] | None = None,
):
    review_row = SimpleNamespace(structured_output={"sections": {"overall": "缩量整理"}})
    pillars_mock = AsyncMock(return_value=pillars)
    anchors_mock = AsyncMock(return_value=anchors or ({}, []))
    patches = (
        patch(
            "app.repositories.review.ai_analysis_repository.load_latest_success",
            AsyncMock(return_value=review_row),
        ),
        patch(
            "app.services.review.limit_up_ai_service.get_cached_attribution",
            AsyncMock(return_value=None),
        ),
        patch.object(agent_plan_input, "_stock_anomalies", AsyncMock(return_value=[])),
        patch.object(agent_plan_input, "_manual_removed_codes", AsyncMock(return_value=[])),
        patch.object(agent_plan_input, "_local_positions", AsyncMock(return_value=[])),
        patch.object(agent_plan_input, "_active_memories", AsyncMock(return_value=[])),
        patch(
            "app.services.trading.agent_plan_input.agent_methodology.build_methodology_input",
            AsyncMock(return_value=None),
        ),
        patch.object(agent_plan_input, "_long_term_pillars", pillars_mock),
        patch.object(agent_plan_input, "_price_anchors", anchors_mock),
    )
    return patches, pillars_mock, anchors_mock


def _enter_all(stack: ExitStack, patches) -> None:
    for p in patches:
        stack.enter_context(p)


@pytest.mark.asyncio
async def test_weekly_agent_gets_pillars_section() -> None:
    """weekly cadence（long-line）注入 long_term_pillars，候选并入锚点宇宙。"""
    pillars = {
        "candidates": [{"stock_code": "sh600000", "score": 5.0}],
        "chain_alerts": [],
    }
    with ExitStack() as stack:
        patches, _, anchors_mock = _collect_patches(
            pillars=pillars,
            anchors=({"sh600000": {"close": 10.0}}, []),
        )
        _enter_all(stack, patches)
        plan_input, _ = await agent_plan_input.collect_plan_input(
            AsyncMock(), _weekly_agent(), 7, _TRADE_DATE
        )
        anchor_codes = anchors_mock.await_args.args[1]

    assert plan_input["long_term_pillars"] == pillars
    assert anchor_codes == ["sh600000"]


@pytest.mark.asyncio
async def test_daily_agent_skips_pillars() -> None:
    """daily cadence（短线）不触发三支柱取数，section 为 None。"""
    with ExitStack() as stack:
        patches, pillars_mock, _ = _collect_patches()
        _enter_all(stack, patches)
        plan_input, _ = await agent_plan_input.collect_plan_input(
            AsyncMock(), _daily_agent(), 7, _TRADE_DATE
        )
        pillars_mock.assert_not_awaited()

    assert plan_input["long_term_pillars"] is None


@pytest.mark.asyncio
async def test_unanchored_candidate_dropped() -> None:
    """无价格锚点的候选从三支柱清单剔除（与异动清单同一约束）。"""
    pillars = {
        "candidates": [
            {"stock_code": "sh600000", "score": 5.0},
            {"stock_code": "sz300001", "score": 1.0},
        ],
        "chain_alerts": [],
    }
    with ExitStack() as stack:
        patches, _, _ = _collect_patches(
            pillars=pillars,
            anchors=({"sh600000": {"close": 10.0}}, ["sz300001"]),
        )
        _enter_all(stack, patches)
        plan_input, _ = await agent_plan_input.collect_plan_input(
            AsyncMock(), _weekly_agent(), 7, _TRADE_DATE
        )

    codes = [c["stock_code"] for c in plan_input["long_term_pillars"]["candidates"]]
    assert codes == ["sh600000"]
    assert "sz300001" in plan_input["unanchored_codes"]


# ---------- _long_term_pillars 内部组装 ----------


def _mapping_node(stock_code: str) -> tuple[SimpleNamespace, SimpleNamespace]:
    mapping = SimpleNamespace(stock_code=stock_code, chain_position="上游设备", revenue_ratio=0.35)
    node = SimpleNamespace(
        industry="半导体",
        node_name="光刻机",
        node_type="upstream",
        avg_gross_margin=45.0,
        revenue_growth=20.0,
        bargaining_power=80.0,
        localization_rate=15.0,
    )
    return mapping, node


def _alert(industry: str, severity: int, signal: str) -> SimpleNamespace:
    return SimpleNamespace(
        industry=industry,
        alert_type="bottleneck",
        severity=severity,
        title=f"{industry}环节紧张",
        description="国产替代加速",
        affected_segments=["光刻机"],
        related_stock_codes=["sh600000", "sz000001"],
        signal_date=date.fromisoformat(signal),
    )


@pytest.mark.asyncio
async def test_pillars_composition_and_degradation() -> None:
    """财务 covered 双态 + 异常降级；图谱挂载与未命中 null；提醒合流截断。"""
    candidates = [
        {"stock_code": "sh600000", "score": 5.0},
        {"stock_code": "sz300001", "score": 1.0},
        {"stock_code": "sh600999", "score": 0.5},
    ]
    health_covered = SimpleNamespace(
        report_date=date(2026, 9, 30), metrics={"roe": 12.5, "gross_margin": 40.0}
    )
    health_uncovered = SimpleNamespace(report_date=None, metrics=None)

    async def _get_health(session, stock_code, report_date=None):
        if stock_code == "sh600000":
            return health_covered
        if stock_code == "sz300001":
            return health_uncovered
        raise RuntimeError("db down")

    with (
        patch(
            "app.services.trading.long_term_screener.screen_long_term_candidates",
            AsyncMock(return_value=candidates),
        ),
        patch(
            "app.repositories.chain.industry_chain_repository.get_mappings_by_codes",
            AsyncMock(return_value=[_mapping_node("sh600000")]),
        ),
        patch(
            "app.repositories.chain.industry_chain_repository.list_refresh_targets",
            AsyncMock(return_value=[("半导体", [1]), ("创新药", [1])]),
        ),
        patch(
            "app.repositories.chain.chain_alert_repository.list_alerts",
            AsyncMock(
                side_effect=lambda session, industry, days=30: (
                    [_alert(industry, 4, "2026-10-15"), _alert(industry, 3, "2026-10-16")]
                    if industry == "半导体"
                    else [_alert(industry, 5, "2026-10-14")]
                )
            ),
        ),
        patch(
            "app.services.market.financial_service.get_health",
            AsyncMock(side_effect=_get_health),
        ),
    ):
        pillars = await agent_plan_input._long_term_pillars(AsyncMock(), _TRADE_DATE)

    by_code = {c["stock_code"]: c for c in pillars["candidates"]}
    assert by_code["sh600000"]["financial_health"]["covered"] is True
    assert by_code["sh600000"]["financial_health"]["metrics"]["roe"] == 12.5
    assert by_code["sz300001"]["financial_health"] == {"covered": False}
    assert by_code["sh600999"]["financial_health"] == {"covered": False}

    assert by_code["sh600000"]["chain_position"][0]["node_name"] == "光刻机"
    assert by_code["sh600000"]["chain_position"][0]["revenue_ratio"] == 0.35
    assert by_code["sz300001"]["chain_position"] is None
    assert by_code["sh600999"]["chain_position"] is None

    alerts = pillars["chain_alerts"]
    assert len(alerts) == 3  # 半导体 2 条 + 创新药 1 条，未触及 Top-N 截断
    severities = [a["severity"] for a in alerts]
    assert severities == sorted(severities, reverse=True)
    assert all(a["industry"] in ("半导体", "创新药") for a in alerts)


@pytest.mark.asyncio
async def test_pillars_chain_lookup_failure_degrades() -> None:
    """图谱/提醒取数失败不阻塞：chain_position 全 null、alerts 空、候选保留。"""
    candidates = [{"stock_code": "sh600000", "score": 5.0}]
    with (
        patch(
            "app.services.trading.long_term_screener.screen_long_term_candidates",
            AsyncMock(return_value=candidates),
        ),
        patch(
            "app.repositories.chain.industry_chain_repository.get_mappings_by_codes",
            AsyncMock(side_effect=RuntimeError("db down")),
        ),
        patch(
            "app.repositories.chain.industry_chain_repository.list_refresh_targets",
            AsyncMock(side_effect=RuntimeError("db down")),
        ),
        patch(
            "app.services.market.financial_service.get_health",
            AsyncMock(return_value=SimpleNamespace(report_date=None, metrics=None)),
        ),
    ):
        pillars = await agent_plan_input._long_term_pillars(AsyncMock(), _TRADE_DATE)

    assert pillars["chain_alerts"] == []
    assert pillars["candidates"][0]["chain_position"] is None
    assert pillars["candidates"][0]["financial_health"] == {"covered": False}
