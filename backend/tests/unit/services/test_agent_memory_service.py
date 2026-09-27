"""agent_memory_service 单元测试：手动沉淀 + 复盘经验自动沉淀（批次 9）。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import NotFoundError
from app.services.trading import agent_memory_service
from app.services.trading.agent_review_service import ReviewExperience

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_create_memory_builds_manual_active_row() -> None:
    session = AsyncMock()
    with patch(
        "app.services.trading.agent_registry.get_agent",
        AsyncMock(return_value=MagicMock()),
    ):
        row = await agent_memory_service.create_memory(
            session, "short-line", title="不追高", body="偏离买点不追", mem_type="lesson"
        )

    assert row.agent_key == "short-line"
    assert row.source == "manual"
    assert row.status == "active"
    assert row.source_result_id is None
    session.add.assert_called_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_memory_unknown_agent_raises() -> None:
    session = AsyncMock()
    with patch(
        "app.services.trading.agent_registry.get_agent",
        AsyncMock(side_effect=NotFoundError("交易 Agent nope 不存在")),
    ):
        with pytest.raises(NotFoundError):
            await agent_memory_service.create_memory(
                session, "nope", title="t", body="b", mem_type="method"
            )
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_delete_memory_removes_row() -> None:
    session = AsyncMock()
    session.get = AsyncMock(return_value=MagicMock(agent_key="short-line"))

    await agent_memory_service.delete_memory(session, "short-line", memory_id=3)

    session.delete.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_memory_missing_or_wrong_agent_raises() -> None:
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    with pytest.raises(NotFoundError):
        await agent_memory_service.delete_memory(session, "short-line", memory_id=99)
    session.delete.assert_not_awaited()

    session.get = AsyncMock(return_value=MagicMock(agent_key="other"))
    with pytest.raises(NotFoundError):
        await agent_memory_service.delete_memory(session, "short-line", memory_id=3)
    session.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_sediment_empty_returns_zero() -> None:
    session = AsyncMock()
    assert (
        await agent_memory_service.sediment_experiences(
            session, "short-line", experiences=[], source_result_id=42
        )
        == 0
    )
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_sediment_filters_blank_and_returns_rowcount() -> None:
    session = AsyncMock()
    execute_result = MagicMock()
    execute_result.rowcount = 1
    session.execute = AsyncMock(return_value=execute_result)
    experiences = [
        ReviewExperience(title="禁止追高", body="偏离买点不追", mem_type="lesson"),
        ReviewExperience(title="", body="无标题", mem_type="method"),
        ReviewExperience(title="空正文", body="   ", mem_type="method"),
    ]

    count = await agent_memory_service.sediment_experiences(
        session, "short-line", experiences=experiences, source_result_id=42
    )

    assert count == 1
    session.execute.assert_awaited_once()
    stmt = session.execute.await_args.args[0]
    assert "on conflict" in str(stmt).lower()
