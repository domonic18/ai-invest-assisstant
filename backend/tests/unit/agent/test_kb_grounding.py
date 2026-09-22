"""KB 引用契约校验单测：CITATION_RE 正反例、缺口判定与弃权回填。"""

import pytest

from app.agent.skills.kb_grounding import (
    MARKET_REQUIRED,
    SENTINEL_LINE,
    STOCK_REQUIRED,
    apply_sentinels,
    citation_gaps,
    warning_lines,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# CITATION_RE
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "按《趋势理论》第36集 08:15（关键位与拐点）确认突破有效",
        "《趋势理论》第12集 03:20-05:40 讲解量价背离",
        "参考《趋势理论》第204页（第三章 支撑压力）",
        "《趋势理论》第 12 集 09:30（趋势判断）",  # 集数含空格由 [^。\n]{0,40} 兜住
    ],
)
def test_citation_regex_matches_tool_and_handbook_forms(text: str) -> None:
    assert citation_gaps({"s": text}, ("s",)) == []


@pytest.mark.parametrize(
    "text",
    [
        "只提书名《趋势理论》无定位",
        "时间码缺书名：第36集 08:15",
        "《趋势理论》见上一章。第36集 08:15",  # 句号截断间隔
        "",
    ],
)
def test_citation_regex_rejects_partial_forms(text: str) -> None:
    assert citation_gaps({"s": text}, ("s",)) == ["s"]


# ---------------------------------------------------------------------------
# citation_gaps / apply_sentinels / warning_lines
# ---------------------------------------------------------------------------


def test_gaps_returns_missing_and_ungrounded_keys_in_order() -> None:
    contents = {
        "technical_analysis": "通道下行 —— 《趋势理论》第36集 08:15",
        "risk_advice": SENTINEL_LINE,
    }
    assert citation_gaps(contents, MARKET_REQUIRED) == []
    assert citation_gaps({"risk_advice": "无引用"}, MARKET_REQUIRED) == [
        "technical_analysis",
        "risk_advice",
    ]


def test_gaps_skip_keys_not_in_contents() -> None:
    """分区整体缺失视为缺口（由 apply_sentinels 兜底为弃权行）。"""
    assert citation_gaps({}, STOCK_REQUIRED) == ["strategy", "risk_lines"]


def test_apply_sentinels_appends_only_to_gaps() -> None:
    contents = {
        "strategy": "策略",
        "risk_lines": "止损 —— 《趋势理论》第12集 03:20",
    }
    out = apply_sentinels(contents, ["strategy"])
    assert out["strategy"] == f"策略\n\n{SENTINEL_LINE}"
    assert out["risk_lines"] == contents["risk_lines"]
    # 入参不被改动
    assert contents["strategy"] == "策略"


def test_apply_sentinels_fills_empty_section() -> None:
    out = apply_sentinels({"strategy": ""}, ["strategy"])
    assert out["strategy"] == SENTINEL_LINE


def test_sentinel_satisfies_contract_roundtrip() -> None:
    contents = apply_sentinels({"a": "x", "b": "y"}, ["a", "b"])
    assert citation_gaps(contents, ("a", "b")) == []


def test_warning_lines_covers_each_gap() -> None:
    lines = warning_lines(["strategy", "risk_lines"])
    assert lines == [
        "分区 strategy 未引用知识库且未声明无适用方法论",
        "分区 risk_lines 未引用知识库且未声明无适用方法论",
    ]
