"""判断模型契约测试：题型校验、to_wire 形状、阈值组解析（D23）。"""

import pytest
from pydantic import ValidationError

from app.core.decision_model import (
    DEFAULT_THRESHOLDS,
    DecisionModelConfigError,
    DecisionThresholds,
    JudgeChoice,
    JudgeChoiceAnswer,
    JudgeNoul,
    JudgeNoulAnswer,
    JudgeNoulCriteria,
    JudgeScore,
    JudgeScoreAnswer,
    thresholds_from_extra,
)

pytestmark = pytest.mark.unit


class TestJudgeQuestions:
    def test_noul_criteria_alias_and_populate_by_name(self) -> None:
        by_alias = JudgeNoulCriteria(**{"true": "真", "false": "假"})
        by_name = JudgeNoulCriteria(criterion_true="真", criterion_false="假")
        assert by_alias == by_name

    def test_noul_to_wire_uses_alias_keys(self) -> None:
        q = JudgeNoul(
            instructions="是否放量突破",
            criteria=JudgeNoulCriteria(criterion_true="放量突破", criterion_false="未突破"),
        )
        assert q.to_wire() == {
            "type": "noul",
            "instructions": "是否放量突破",
            "criteria": {"true": "放量突破", "false": "未突破"},
        }

    def test_choice_option_count_bounds(self) -> None:
        criteria = {"a": "甲", "b": "乙"}
        assert JudgeChoice(instructions="选一", criteria=criteria).to_wire()["type"] == "choice"
        with pytest.raises(ValidationError):
            JudgeChoice(instructions="选一", criteria={"only": "唯一项"})
        # 256 项越上界
        with pytest.raises(ValidationError):
            JudgeChoice(instructions="选一", criteria={f"k{i}": str(i) for i in range(256)})

    def test_score_level_count_bounds(self) -> None:
        assert JudgeScore(instructions="打分", criteria=["低", "高"]).to_wire()["type"] == "score"
        with pytest.raises(ValidationError):
            JudgeScore(instructions="打分", criteria=["唯一级"])
        with pytest.raises(ValidationError):
            JudgeScore(instructions="打分", criteria=[str(i) for i in range(11)])

    def test_noul_answer_has_no_confidence(self) -> None:
        """Noul 无 confidence 字段——数字本身即信念（§11.3 铁律）。"""
        assert "confidence" not in JudgeNoulAnswer.model_fields
        answer = JudgeNoulAnswer(type="noul", noul=0.14)
        assert not hasattr(answer, "confidence")

    def test_answer_types_carry_confidence(self) -> None:
        assert "confidence" in JudgeChoiceAnswer.model_fields
        assert "confidence" in JudgeScoreAnswer.model_fields


class TestDecisionThresholds:
    def test_default_thresholds(self) -> None:
        assert DEFAULT_THRESHOLDS.observe == 0.6
        assert DEFAULT_THRESHOLDS.fund_action == 0.85
        assert DEFAULT_THRESHOLDS.exit_action == 0.6

    def test_range_and_ordering_validation(self) -> None:
        DecisionThresholds(observe=0.5, fund_action=0.9)
        # 离场档边界合法：贴观察档 / 贴资金档
        DecisionThresholds(observe=0.5, fund_action=0.9, exit_action=0.5)
        DecisionThresholds(observe=0.5, fund_action=0.9, exit_action=0.9)
        for observe, fund in [(0.0, 0.9), (1.0, 0.9), (-0.1, 0.9), (0.6, 0.6), (0.7, 0.6)]:
            with pytest.raises(ValidationError):
                DecisionThresholds(observe=observe, fund_action=fund)
        # 离场档越界：低于观察档 / 高于资金档
        for exit_action in [0.4, 0.95]:
            with pytest.raises(ValidationError):
                DecisionThresholds(observe=0.6, fund_action=0.85, exit_action=exit_action)


class TestThresholdsFromExtra:
    def test_missing_returns_default(self) -> None:
        assert thresholds_from_extra({}) == DEFAULT_THRESHOLDS
        assert thresholds_from_extra({"thresholds": None}) == DEFAULT_THRESHOLDS

    def test_valid_custom(self) -> None:
        thresholds = thresholds_from_extra(
            {"thresholds": {"observe": 0.5, "fund_action": 0.9}}
        )
        assert thresholds == DecisionThresholds(observe=0.5, fund_action=0.9)
        # exit_action 可选覆盖，缺省回起步档
        custom = thresholds_from_extra(
            {"thresholds": {"observe": 0.5, "fund_action": 0.9, "exit_action": 0.7}}
        )
        assert custom.exit_action == 0.7

    def test_invalid_shapes_raise_config_error(self) -> None:
        for extra in [
            {"thresholds": "high"},
            {"thresholds": {"observe": 0.5}},  # 缺 fund_action
            {"thresholds": {"observe": None, "fund_action": 0.9}},  # 类型非法
            {"thresholds": {"observe": 0, "fund_action": 0.9}},  # 越下界
            {"thresholds": {"observe": 0.9, "fund_action": 0.5}},  # 档位倒挂
        ]:
            with pytest.raises(DecisionModelConfigError):
                thresholds_from_extra(extra)
