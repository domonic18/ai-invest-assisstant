"""skill 体系公共包：registry（builtin 登记）与 prompt（提示词加载）。

纯数据与文件 IO，不导入 agent 执行代码；services 与 agent 层均可顶层导入。
"""

from app.skills.prompt import load_skill_prompt, reload_skill_prompt
from app.skills.registry import (
    BUILTIN_SKILLS,
    SkillDescriptor,
    builtin_skill_ids,
    get_skill,
    iter_skills,
)

__all__ = [
    "BUILTIN_SKILLS",
    "SkillDescriptor",
    "builtin_skill_ids",
    "get_skill",
    "iter_skills",
    "load_skill_prompt",
    "reload_skill_prompt",
]
