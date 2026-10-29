"""多周期复盘专属板块契约测试（注册表装载 / 渲染 / 规范化校验）。"""

import pytest

from app.services.trading.agent_review_periods import REVIEW_PERIODS
from app.services.trading.agent_review_sections import (
    ReviewSection,
    canonicalize_sections,
    contract_text,
    render_section_instructions,
    section_specs,
)


@pytest.mark.unit
class TestSectionRegistry:
    def test_every_period_has_sections(self) -> None:
        """六档周期都必须有专属板块（yaml 契约与代码周期词表一致）。"""
        for period in REVIEW_PERIODS:
            specs = section_specs(period)
            assert specs, period
            assert len({spec.key for spec in specs}) == len(specs)

    def test_contract_mentions_metrics_as_sole_source(self) -> None:
        text = contract_text()
        assert "metrics" in text
        assert "唯一数值来源" in text

    def test_render_section_instructions_lists_ordered_specs(self) -> None:
        rendered = render_section_instructions("quarter")
        specs = section_specs("quarter")
        assert rendered.splitlines()[0].startswith("本周期专属板块")
        for index, spec in enumerate(specs, start=1):
            assert f"{index}. {spec.key}（{spec.title}）" in rendered


@pytest.mark.unit
class TestCanonicalizeSections:
    def test_reorders_and_restores_registry_titles(self) -> None:
        """顺序按注册表归一，标题以注册表为准，正文保留 LLM 输出。"""
        specs = section_specs("day")
        sections = [
            ReviewSection(key=specs[0].key, title="改写标题", body="实质分析")
        ]
        result = canonicalize_sections("day", sections)
        assert [item.key for item in result] == [spec.key for spec in specs]
        assert result[0].title == specs[0].title
        assert result[0].body == "实质分析"

    def test_rejects_missing_key(self) -> None:
        first = section_specs("quarter")[0]
        with pytest.raises(ValueError, match="专属板块不符"):
            canonicalize_sections(
                "quarter", [ReviewSection(key=first.key, title=first.title, body="x")]
            )

    def test_rejects_extra_key(self) -> None:
        specs = section_specs("day")
        sections = [
            *(ReviewSection(key=spec.key, title=spec.title, body="x") for spec in specs),
            ReviewSection(key="invented", title="编造", body="x"),
        ]
        with pytest.raises(ValueError, match="专属板块不符"):
            canonicalize_sections("day", sections)

    def test_rejects_duplicate_key(self) -> None:
        spec = section_specs("day")[0]
        duplicate = ReviewSection(key=spec.key, title=spec.title, body="x")
        with pytest.raises(ValueError, match="专属板块不符"):
            canonicalize_sections("day", [duplicate, duplicate])
