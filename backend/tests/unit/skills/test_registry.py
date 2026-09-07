"""builtin skill 注册表一致性单测：注册表 ↔ 文件资产 ↔ 代码硬编码三方钉死。"""

import re
from importlib.util import find_spec
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.skills import BUILTIN_SKILLS, builtin_skill_ids, get_skill
from app.skills.prompt import load_skill_prompt

_BACKEND_DIR = Path(__file__).resolve().parents[3]
_SKILL_ID_DECL_RE = re.compile(r'^(?:_SUMMARY_)?SKILL_ID = "([a-z0-9-]+)"', re.MULTILINE)


@pytest.mark.unit
class TestRegistryIntegrity:
    def test_skill_ids_unique(self) -> None:
        ids = [d.skill_id for d in BUILTIN_SKILLS]
        assert len(ids) == len(set(ids))

    def test_declared_files_exist(self) -> None:
        """skill_md=True 必有 SKILL.md；executable/prompt_only 必有 prompt.yaml。"""
        skills_dir = get_settings().skills_dir
        for d in BUILTIN_SKILLS:
            skill_dir = skills_dir / d.skill_id
            assert skill_dir.is_dir(), f"{d.skill_id} 目录缺失"
            if d.skill_md:
                assert (skill_dir / "SKILL.md").exists(), f"{d.skill_id} 缺 SKILL.md"
            if d.kind in ("executable", "prompt_only"):
                assert (skill_dir / "prompt.yaml").exists(), f"{d.skill_id} 缺 prompt.yaml"

    def test_no_orphan_skill_assets(self) -> None:
        """磁盘上的 skill 资产必须全部登记（防目录/registry 单侧漂移）。"""
        skills_dir = get_settings().skills_dir
        disk_skill_md = {p.parent.name for p in skills_dir.glob("*/SKILL.md")}
        registered_skill_md = {d.skill_id for d in BUILTIN_SKILLS if d.skill_md}
        assert disk_skill_md == registered_skill_md

        disk_prompts = {p.parent.name for p in skills_dir.glob("*/prompt.yaml")}
        registered_prompts = {
            d.skill_id for d in BUILTIN_SKILLS if d.kind in ("executable", "prompt_only")
        }
        assert disk_prompts == registered_prompts

    def test_get_skill_lookup(self) -> None:
        assert get_skill("market-daily-review") is not None
        assert get_skill("no-such-skill") is None

    def test_executor_modules_resolvable(self) -> None:
        """executor 字符串引用必须能解析到真实模块（防改名漂移）。"""
        for d in BUILTIN_SKILLS:
            if d.executor:
                assert find_spec(d.executor) is not None, f"{d.skill_id} executor 不存在: {d.executor}"

    def test_task_spec_names_match_collector(self) -> None:
        """task_spec_name 集合 == collector AI 任务声明的全部 TaskSpec name。"""
        from collector.runtime.specs.ai import SPECS

        spec_names = {spec.name for spec in SPECS}
        mapped = {d.task_spec_name for d in BUILTIN_SKILLS if d.task_spec_name}
        assert mapped == spec_names


@pytest.mark.unit
class TestHardcodedSkillIds:
    def test_code_skill_ids_subset_of_registry(self) -> None:
        """agent 执行器与服务层硬编码的 SKILL_ID 必须已登记（防 id 漂移）。"""
        paths = list((_BACKEND_DIR / "app" / "agent" / "skills").glob("*.py"))
        paths += list((_BACKEND_DIR / "app" / "services").rglob("*.py"))
        assert paths, "未扫描到任何文件，目录结构可能已变更"

        declared: set[str] = set()
        for path in paths:
            declared.update(_SKILL_ID_DECL_RE.findall(path.read_text(encoding="utf-8")))
        assert declared, "未扫描到任何 SKILL_ID 声明，正则可能失效"
        assert declared <= builtin_skill_ids()


@pytest.mark.unit
class TestSkillPromptLoading:
    def test_all_registered_prompts_loadable(self) -> None:
        for d in BUILTIN_SKILLS:
            if d.kind in ("executable", "prompt_only"):
                config = load_skill_prompt(d.skill_id)
                assert config.id == d.skill_id
                assert config.system_prompt.strip()

    def test_load_unregistered_prompt_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_skill_prompt("no-such-skill")

    def test_module_cache_effective(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """同 id 二次 load 命中模块缓存，不再触碰文件系统。"""
        from app.skills import prompt as prompt_module

        first = load_skill_prompt("market-daily-review")

        def _fail(skill_id: str) -> Path:
            raise AssertionError("缓存未生效：二次 load 仍试图解析文件路径")

        monkeypatch.setattr(prompt_module, "_prompt_path", _fail)
        assert load_skill_prompt("market-daily-review") is first
