"""助手会话服务：``assistant_session`` CRUD、线程删除（级联 checkpoint）、
Skill 摘要解析。消息轨迹由 LangGraph checkpoint 承载，不落业务表。
"""

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.assistant_session import AssistantSession
from app.repositories.assistant.session_repository import AssistantSessionRepository
from app.repositories.skill import SkillRepository, UserSkillRepository
from app.schemas.assistant import SkillSummary
from app.skills import iter_skills

logger = structlog.get_logger(__name__)


class AssistantService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = AssistantSessionRepository(session)

    async def create_session(
        self, user_id: int, title: str | None = None
    ) -> AssistantSession:
        """新建会话；id 即 Agent Protocol thread_id。"""
        row = AssistantSession(id=uuid.uuid4(), user_id=user_id, title=title)
        self._repo.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def list_sessions(
        self, user_id: int, limit: int = 20, offset: int = 0
    ) -> tuple[list[AssistantSession], int]:
        """当前用户会话列表（最近活跃优先）与总数。"""
        return await self._repo.list_by_user(user_id, limit, offset)

    async def get_session(
        self, user_id: int, thread_id: str
    ) -> AssistantSession | None:
        """按归属取会话；thread_id 非法或非本人返回 None。"""
        try:
            tid = uuid.UUID(thread_id)
        except ValueError:
            return None
        return await self._repo.get_by_user_and_thread(user_id, tid)

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

    async def list_skills(self, user_id: int) -> list[SkillSummary]:
        """builtin 技能摘要（registry 驱动）+ 用户已启用 custom 技能。"""
        skills_dir = get_settings().skills_dir
        summaries: list[SkillSummary] = []
        for descriptor in iter_skills():
            if not descriptor.skill_md:
                continue
            path = skills_dir / descriptor.skill_id / "SKILL.md"
            if not path.exists():
                continue
            parsed = parse_skill_file(path)
            summaries.append(
                SkillSummary(
                    id=parsed["id"],
                    name=parsed["name"],
                    description=parsed["description"],
                    kind=descriptor.kind,
                    is_custom=False,
                )
            )
        summaries.extend(await self.list_enabled_custom_skills(user_id))
        return summaries

    async def list_enabled_custom_skills(self, user_id: int) -> list[SkillSummary]:
        """用户已安装且启用的 custom 技能摘要（助手上下文注入数据源）。"""
        installs = await UserSkillRepository(self._session).list_installed(user_id)
        enabled_ids = [item.skill_id for item in installs if item.enabled]
        if not enabled_ids:
            return []
        rows = await SkillRepository(self._session).get_by_skill_ids(enabled_ids)
        summaries: list[SkillSummary] = []
        for row in rows:
            if row.is_builtin:
                continue
            definition = row.custom_definition or {}
            description = row.description or str(
                definition.get("skill_md") or ""
            ).strip()[:120]
            summaries.append(
                SkillSummary(
                    id=row.skill_id,
                    name=row.label,
                    description=description,
                    kind="custom",
                    is_custom=True,
                )
            )
        return summaries

    async def custom_skill_index_lines(self, user_id: int) -> list[str]:
        """已启用 custom 技能的索引行（渐进披露：每技能一行，全文不注入）。"""
        return [
            f"{summary.name}：{summary.description}" if summary.description else summary.name
            for summary in await self.list_enabled_custom_skills(user_id)
        ]


async def touch_session_standalone(thread_id: str, title: str | None) -> None:
    """run 结束后用独立 session 回写 last_message_at/标题；失败只记日志。

    供 SSE 流收尾（可能处于取消传播上下文）调用，自管连接生命周期。
    """
    from app.core.database import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            await AssistantService(db).touch_session(thread_id, title)
    except Exception as exc:  # noqa: BLE001
        logger.warning("assistant_touch_failed", thread_id=thread_id, error=str(exc))


def derive_session_title(messages_in: list[dict[str, Any]]) -> str | None:
    """取首条用户消息前 20 字作会话标题（纯 str 或 text 块列表均可）。"""
    if not messages_in:
        return None
    content = messages_in[0].get("content")
    if isinstance(content, str):
        return content[:20]
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                return str(block["text"])[:20]
    return None


async def finalize_run(thread_id: str, messages_in: list[dict[str, Any]]) -> None:
    """SSE 流收尾：派生标题并回写会话活跃时间。

    用户取消时本任务已收到 CancelledError，若在取消上下文里直接操作数据库，
    会把 SQLAlchemy 池中的 asyncpg 连接打断成脏连接，导致后续请求 500
    （connection is closed）。放独立任务 + shield，让回写在取消传播之外完成。
    """
    touch = asyncio.create_task(
        touch_session_standalone(thread_id, derive_session_title(messages_in))
    )
    try:
        await asyncio.shield(touch)
    except Exception:  # noqa: BLE001  # 失败已在任务内记录
        pass


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
