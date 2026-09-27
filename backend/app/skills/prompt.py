"""skill 提示词契约加载：``skills/<skill_id>/<filename>.yaml``。

skill 提示词是 skill 分发单元（``skills/<skill_id>/`` 目录）的一部分；
本模块提供模块级缓存的加载入口，修复原各调用点每次新建 ``PromptLoader``
导致实例级缓存失效的问题。同一技能包可承载多份 prompt（如复盘
``review_prompt.yaml``，D34），缓存键 = ``skill_id:filename``。
"""

from pathlib import Path

import yaml

from app.agent.core.prompt_loader import PromptConfig
from app.core.config import get_settings

_cache: dict[str, PromptConfig] = {}


def load_skill_prompt(skill_id: str) -> PromptConfig:
    """加载 builtin skill 的主提示词契约（prompt.yaml，模块级缓存）。

    Raises:
        FileNotFoundError: skill 未登记 prompt.yaml 时抛出。
    """
    return load_named_skill_prompt(skill_id, "prompt.yaml")


def load_named_skill_prompt(skill_id: str, filename: str) -> PromptConfig:
    """加载 skill 目录下指定文件名的提示词契约（缓存键 skill_id:filename）。

    filename 须为包内固定资产名（调用方硬编码，非用户输入），无路径穿越面。

    Raises:
        FileNotFoundError: 目标 YAML 不存在时抛出。
    """
    cache_key = f"{skill_id}:{filename}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    path = _prompt_path(skill_id, filename)
    if not path.exists():
        raise FileNotFoundError(f"Skill prompt not found: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    config = PromptConfig(**data)
    _cache[cache_key] = config
    return config


def reload_skill_prompt(skill_id: str, filename: str = "prompt.yaml") -> PromptConfig:
    """失效缓存并重新加载（prompt 热更新/测试用）。"""
    _cache.pop(f"{skill_id}:{filename}", None)
    return load_named_skill_prompt(skill_id, filename)


def _prompt_path(skill_id: str, filename: str = "prompt.yaml") -> Path:
    return get_settings().skills_dir / skill_id / filename
