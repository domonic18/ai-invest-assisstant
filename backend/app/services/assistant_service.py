"""助手会话服务：``assistant_session`` CRUD、线程删除（级联 checkpoint）、
Skill 摘要解析。消息轨迹由 LangGraph checkpoint 承载，不落业务表。
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.assistant_session import AssistantSession
from app.schemas.assistant import SkillSummary

logger = structlog.get_logger(__name__)


class AssistantService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_session(
        self, user_id: int, title: str | None = None
    ) -> AssistantSession:
        """新建会话；id 即 Agent Protocol thread_id。"""
        row = AssistantSession(id=uuid.uuid4(), user_id=user_id, title=title)
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def list_sessions(
        self, user_id: int, limit: int = 20, offset: int = 0
    ) -> tuple[list[AssistantSession], int]:
        """当前用户会话列表（最近活跃优先）与总数。"""
        base = select(AssistantSession).where(AssistantSession.user_id == user_id)
        rows = (
            await self._session.execute(
                base.order_by(
                    AssistantSession.last_message_at.desc().nulls_last(),
                    AssistantSession.created_at.desc(),
                )
                .limit(limit)
                .offset(offset)
            )
        ).scalars().all()
        total = (
            await self._session.execute(
                select(func.count()).select_from(AssistantSession).where(
                    AssistantSession.user_id == user_id
                )
            )
        ).scalar_one()
        return list(rows), total

    async def get_session(
        self, user_id: int, thread_id: str
    ) -> AssistantSession | None:
        """按归属取会话；thread_id 非法或非本人返回 None。"""
        try:
            tid = uuid.UUID(thread_id)
        except ValueError:
            return None
        return (
            await self._session.execute(
                select(AssistantSession).where(
                    AssistantSession.id == tid,
                    AssistantSession.user_id == user_id,
                )
            )
        ).scalar_one_or_none()

    async def touch_session(self, thread_id: str, title: str | None = None) -> None:
        """run 结束后回写 last_message_at；首次对话补标题（取首条消息前 20 字）。"""
        try:
            tid = uuid.UUID(thread_id)
        except ValueError:
            return
        row = await self._session.get(AssistantSession, tid)
        if row is None:
            return
        now = datetime.now(timezone.utc)
        row.last_message_at = now
        row.updated_at = now
        if title and not row.title:
            row.title = title[:128]
        await self._session.commit()

    async def delete_session(self, user_id: int, thread_id: str) -> bool:
        """删除会话：先删 LangGraph checkpoint 线程，再删业务行。"""
        row = await self.get_session(user_id, thread_id)
        if row is None:
            return False

        from app.agent.runtime.assistant_agent import get_checkpointer

        checkpointer = await get_checkpointer()
        await checkpointer.adelete_thread(thread_id)
        await self._session.delete(row)
        await self._session.commit()
        logger.info("assistant_session_deleted", thread_id=thread_id)
        return True

    def list_skills(self) -> list[SkillSummary]:
        """扫描 skills/ 目录并解析 SKILL.md 摘要。"""
        skills_dir = get_settings().skills_dir
        if not skills_dir.exists():
            return []
        return [
            SkillSummary(**parse_skill_file(path))
            for path in sorted(skills_dir.glob("*/SKILL.md"))
        ]


def parse_skill_file(path: Path) -> dict[str, Any]:
    """解析 skills/<id>/SKILL.md 摘要：优先 YAML frontmatter，退化用目录名+首行。"""
    import yaml

    skill_id = path.parent.name
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            try:
                frontmatter = yaml.safe_load(parts[1]) or {}
                if isinstance(frontmatter, dict) and frontmatter.get("name"):
                    return {
                        "id": skill_id,
                        "name": str(frontmatter["name"]),
                        "description": str(frontmatter.get("description", "")),
                    }
            except yaml.YAMLError:
                pass
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return {"id": skill_id, "name": skill_id, "description": stripped[:200]}
    return {"id": skill_id, "name": skill_id, "description": ""}
