"""skill / user_skill 仓储：只做查询构造与执行，事务由服务层管理。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import Skill, UserSkill
from app.repositories.base import BaseRepository


class SkillRepository(BaseRepository[Skill]):
    """技能登记行仓储。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Skill)

    async def get_by_skill_id(self, skill_id: str) -> Skill | None:
        stmt = select(Skill).where(Skill.skill_id == skill_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_skill_ids(self, skill_ids: list[str]) -> list[Skill]:
        if not skill_ids:
            return []
        stmt = select(Skill).where(Skill.skill_id.in_(skill_ids)).order_by(Skill.id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_published(self) -> list[Skill]:
        """广场视图：全部已发布技能（builtin + custom），按 sort、id 稳定排序。"""
        stmt = (
            select(Skill)
            .where(Skill.published.is_(True))
            .order_by(Skill.sort, Skill.id)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_by_owner(self, owner_user_id: int) -> list[Skill]:
        """本人全部 custom 技能（含未发布）。"""
        stmt = (
            select(Skill)
            .where(Skill.owner_user_id == owner_user_id)
            .order_by(Skill.sort, Skill.id)
        )
        return list((await self.session.execute(stmt)).scalars().all())


class UserSkillRepository(BaseRepository[UserSkill]):
    """用户安装关系仓储。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, UserSkill)

    async def list_installed(self, user_id: int) -> list[UserSkill]:
        stmt = (
            select(UserSkill)
            .where(UserSkill.user_id == user_id)
            .order_by(UserSkill.sort, UserSkill.id)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_install(self, user_id: int, skill_id: str) -> UserSkill | None:
        stmt = select(UserSkill).where(
            UserSkill.user_id == user_id, UserSkill.skill_id == skill_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()
