"""builtin skill 启动同步：``app/skills/registry.py`` → ``skill`` 表幂等投影。

builtin 行不做静态 seed（防代码与 seed 漂移，见批次7 设计）：应用启动
``_warmup`` 时按 registry upsert，label/kind/description/published/sort 随
代码演进而更新；**绝不 delete**——防止代码回滚级联删除用户安装关系。
"""


import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.skill import Skill
from app.services.assistant.assistant_service import parse_skill_file
from app.skills import SkillDescriptor, iter_skills

logger = structlog.get_logger(__name__)


def _frontmatter_description(descriptor: SkillDescriptor) -> str | None:
    """从 SKILL.md frontmatter 解析描述；无 SKILL.md 的 skill 返回 None。"""
    if not descriptor.skill_md:
        return None
    path = get_settings().skills_dir / descriptor.skill_id / "SKILL.md"
    if not path.exists():
        return None
    return parse_skill_file(path).get("description") or None


async def sync_builtin_skills(session: AsyncSession) -> None:
    """按注册表顺序幂等 upsert builtin 行；无变更不产生写事务。"""
    stmt = select(Skill).where(Skill.is_builtin.is_(True))
    existing = {
        row.skill_id: row for row in (await session.execute(stmt)).scalars().all()
    }

    inserted = 0
    updated = 0
    for index, descriptor in enumerate(iter_skills(), start=1):
        description = _frontmatter_description(descriptor)
        row = existing.get(descriptor.skill_id)
        if row is not None and not row.is_builtin:
            logger.warning(
                "builtin_skill_sync_skipped_custom_conflict", skill_id=descriptor.skill_id
            )
            continue
        if row is None:
            session.add(
                Skill(
                    skill_id=descriptor.skill_id,
                    label=descriptor.label,
                    kind=descriptor.kind,
                    scenario=descriptor.scenario,
                    description=description,
                    is_builtin=True,
                    published=True,
                    sort=index,
                )
            )
            inserted += 1
        elif (
            row.label,
            row.kind,
            row.scenario,
            row.description,
            row.published,
            row.sort,
        ) != (
            descriptor.label,
            descriptor.kind,
            descriptor.scenario,
            description,
            True,
            index,
        ):
            row.label = descriptor.label
            row.kind = descriptor.kind
            row.scenario = descriptor.scenario
            row.description = description
            row.published = True
            row.sort = index
            updated += 1

    if inserted or updated:
        await session.commit()
    logger.info(
        "builtin_skills_synced", registered=len(tuple(iter_skills())), inserted=inserted, updated=updated
    )
