"""skill 子域服务。"""

from app.services.skill.skill_service import SkillService
from app.services.skill.skill_sync import sync_builtin_skills

__all__ = ["SkillService", "sync_builtin_skills"]
