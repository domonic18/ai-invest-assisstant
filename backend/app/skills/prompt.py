"""skill 提示词契约加载：``skills/<skill_id>/prompt.yaml``。

skill 提示词是 skill 分发单元（``skills/<skill_id>/`` 目录）的一部分；
本模块提供模块级缓存的加载入口，修复原各调用点每次新建 ``PromptLoader``
导致实例级缓存失效的问题。
"""

from pathlib import Path

import yaml

from app.agent.core.prompt_loader import PromptConfig
from app.core.config import get_settings

_cache: dict[str, PromptConfig] = {}


def load_skill_prompt(skill_id: str) -> PromptConfig:
    """加载 builtin skill 的提示词契约（模块级缓存）。

    Raises:
        FileNotFoundError: skill 未登记 prompt.yaml 时抛出。
    """
    cached = _cache.get(skill_id)
    if cached is not None:
        return cached

    path = _prompt_path(skill_id)
    if not path.exists():
        raise FileNotFoundError(f"Skill prompt not found: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    config = PromptConfig(**data)
    _cache[skill_id] = config
    return config


def reload_skill_prompt(skill_id: str) -> PromptConfig:
    """失效缓存并重新加载（prompt 热更新/测试用）。"""
    _cache.pop(skill_id, None)
    return load_skill_prompt(skill_id)


def _prompt_path(skill_id: str) -> Path:
    return get_settings().skills_dir / skill_id / "prompt.yaml"
