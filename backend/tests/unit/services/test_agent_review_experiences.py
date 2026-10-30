"""复盘经验沉淀口径测试（短周期全量 / 长周期只留体系级，§4.6）。"""

import pytest

from app.services.trading.agent_review_content import ReviewExperience
from app.services.trading.agent_review_experiences import filter_period_experiences
from app.services.trading.agent_review_periods import REVIEW_PERIODS


def _experiences() -> list[ReviewExperience]:
    return [
        ReviewExperience(title="止损不过夜", body="收盘前必须挂止损", mem_type="discipline"),
        ReviewExperience(title="缩量回踩买点更优", body="胜率更高", mem_type="method"),
        ReviewExperience(title="某笔追高", body="单笔教训", mem_type="lesson"),
    ]


@pytest.mark.unit
class TestFilterPeriodExperiences:
    @pytest.mark.parametrize("period", ["day", "week", "month"])
    def test_short_periods_keep_all(self, period: str) -> None:
        assert filter_period_experiences(period, _experiences()) == _experiences()  # type: ignore[arg-type]

    @pytest.mark.parametrize("period", ["quarter", "half_year", "year"])
    def test_long_periods_keep_system_level_only(self, period: str) -> None:
        result = filter_period_experiences(period, _experiences())  # type: ignore[arg-type]
        assert [item.mem_type for item in result] == ["discipline", "method"]

    def test_all_periods_covered(self) -> None:
        """周期词表与长周期判定保持同步（新增周期必须明确沉淀口径）。"""
        for period in REVIEW_PERIODS:
            assert isinstance(filter_period_experiences(period, []), list)
