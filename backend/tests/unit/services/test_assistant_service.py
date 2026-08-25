"""assistant_service 单测（mock session，不触库）。"""

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.assistant_session import AssistantSession
from app.services.assistant_service import AssistantService, parse_skill_file


def _row(**overrides: object) -> AssistantSession:
    return AssistantSession(
        id=overrides.get("id", uuid.uuid4()),
        user_id=overrides.get("user_id", 1),
        title=overrides.get("title", None),
    )


@pytest.mark.unit
class TestAssistantService:
    @pytest.mark.asyncio
    async def test_create_session_generates_thread_id(self) -> None:
        session = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        row = await AssistantService(session).create_session(user_id=1, title="测试")

        assert isinstance(row.id, uuid.UUID)
        session.add.assert_called_once()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_session_rejects_invalid_uuid(self) -> None:
        session = MagicMock()
        row = await AssistantService(session).get_session(1, "not-a-uuid")
        assert row is None
        session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_touch_session_sets_title_only_when_missing(self) -> None:
        session = MagicMock()
        session.commit = AsyncMock()
        existing = _row(title=None)
        session.get = AsyncMock(return_value=existing)

        service = AssistantService(session)
        await service.touch_session(str(existing.id), "平安银行最近走势如何呀")
        assert existing.title == "平安银行最近走势如何呀"
        assert existing.last_message_at is not None

        titled = _row(title="已有标题")
        session.get = AsyncMock(return_value=titled)
        await service.touch_session(str(titled.id), "新问题")
        assert titled.title == "已有标题"

    @pytest.mark.asyncio
    async def test_delete_session_removes_checkpoint_first(self) -> None:
        session = MagicMock()
        session.delete = AsyncMock()
        session.commit = AsyncMock()
        row = _row()
        checkpointer = MagicMock()
        checkpointer.adelete_thread = AsyncMock()

        with (
            patch.object(
                AssistantService,
                "get_session",
                AsyncMock(return_value=row),
            ),
            patch(
                "app.agent.runtime.assistant_agent.get_checkpointer",
                AsyncMock(return_value=checkpointer),
            ),
        ):
            ok = await AssistantService(session).delete_session(1, str(row.id))

        assert ok is True
        checkpointer.adelete_thread.assert_awaited_once_with(str(row.id))
        session.delete.assert_awaited_once()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_session_returns_false_when_missing(self) -> None:
        session = MagicMock()
        with patch.object(
            AssistantService, "get_session", AsyncMock(return_value=None)
        ):
            ok = await AssistantService(session).delete_session(1, str(uuid.uuid4()))
        assert ok is False


@pytest.mark.unit
class TestParseSkillFile:
    def test_frontmatter_preferred(self, tmp_path: Path) -> None:
        path = tmp_path / "my-skill" / "SKILL.md"
        path.parent.mkdir()
        path.write_text(
            "---\nname: 产业链体检\ndescription: 半导体产业链分析方法论\n---\n\n正文内容",
            encoding="utf-8",
        )
        result = parse_skill_file(path)
        assert result == {
            "id": "my-skill",
            "name": "产业链体检",
            "description": "半导体产业链分析方法论",
        }

    def test_fallback_without_frontmatter(self, tmp_path: Path) -> None:
        path = tmp_path / "legacy" / "SKILL.md"
        path.parent.mkdir()
        path.write_text("# 标题\n\n第一行说明文字", encoding="utf-8")
        result = parse_skill_file(path)
        assert result["id"] == "legacy"
        assert result["name"] == "legacy"
        assert result["description"] == "第一行说明文字"
