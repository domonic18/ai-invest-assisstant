"""skills 渐进披露接入单测：SKILL.md frontmatter 规范与 prompt 契约解析。"""

from pathlib import Path

import pytest

from app.core.config import get_settings
from app.services.assistant.assistant_service import parse_skill_file
from app.skills.prompt import load_skill_prompt

EXPECTED_SKILLS = {
    "anomaly-attribution",
    "chain-breakthrough",
    "financial-health-check",
    "financial-report-summary",
    "hotspot-detection",
    "industry-chain-analysis",
    "limit-up-review",
    "market-daily-review",
    "news-score",
    "news-storyline",
    "news-topic",
    "research-report-summary",
    "stock-daily-analysis",
    "watchlist-screenshot-recognition",
}


def _skills_dir() -> Path:
    path = get_settings().skills_dir
    assert path.exists(), f"skills 目录不存在: {path}"
    return path


@pytest.mark.unit
class TestSkillFrontmatter:
    def test_all_skills_have_standard_frontmatter(self) -> None:
        """每个 SKILL.md 必须有 name/description frontmatter（deepagents 渐进披露依赖）。"""
        for skill_dir in sorted(_skills_dir().iterdir()):
            skill_md = skill_dir / "SKILL.md"
            if not skill_dir.is_dir() or not skill_md.exists():
                continue
            result = parse_skill_file(skill_md)
            assert result["id"] == skill_dir.name
            assert result["name"], f"{skill_dir.name} 缺 frontmatter name"
            assert result["description"], f"{skill_dir.name} 缺 frontmatter description"
            assert len(result["description"]) >= 10

    def test_expected_skill_ids_present(self) -> None:
        ids = {p.parent.name for p in _skills_dir().glob("*/SKILL.md")}
        assert ids == EXPECTED_SKILLS

    def test_skills_dir_exists_for_agent_wiring(self) -> None:
        """assistant_agent 以 skills_dir 存在性决定是否接入渐进披露。"""
        assert get_settings().skills_dir.exists()


@pytest.mark.unit
class TestSkillPromptYaml:
    def test_all_skill_prompts_parse(self) -> None:
        """每个 skills/<id>/prompt.yaml 必须能被 load_skill_prompt 解析为合法 PromptConfig。"""
        yaml_files = sorted(_skills_dir().glob("*/prompt.yaml"))
        assert yaml_files, "skills 下无 prompt.yaml"
        for path in yaml_files:
            config = load_skill_prompt(path.parent.name)
            assert config.system_prompt.strip(), f"{path.parent.name} 缺 system_prompt"
