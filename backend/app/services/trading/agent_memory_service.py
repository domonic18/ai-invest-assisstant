"""交易 Agent 记忆管理服务（plan §12.3：查看 / 编辑 / 停用）。

记忆是 Agent 私有资产（不经 KB）：status='active' 条目由每日计划生成服务
全量注入 prompt（``agent_plan_service._active_memories``）；停用 = archived
（不物理删除，保留归因链路）。手动沉淀（POST）与复盘自动提取随批次 9 接入。
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_now
from app.core.exceptions import NotFoundError
from app.models.agent_trading import AgentMemory


async def list_memories(
    session: AsyncSession, *, status: str | None = None
) -> list[AgentMemory]:
    """记忆清单（缺省全部状态，按新近度倒序）。"""
    stmt = select(AgentMemory).order_by(AgentMemory.updated_at.desc())
    if status is not None:
        stmt = stmt.where(AgentMemory.status == status)
    rows = await session.execute(stmt)
    return list(rows.scalars().all())


async def update_memory(
    session: AsyncSession,
    *,
    memory_id: int,
    title: str | None = None,
    body: str | None = None,
    mem_type: str | None = None,
) -> AgentMemory:
    """编辑记忆（标题/正文/类型，未提供字段不变）。

    Raises:
        NotFoundError: 记忆不存在
    """
    row = await session.get(AgentMemory, memory_id)
    if row is None:
        raise NotFoundError(f"记忆 {memory_id} 不存在")
    if title is not None:
        row.title = title
    if body is not None:
        row.body = body
    if mem_type is not None:
        row.mem_type = mem_type
    row.updated_at = utc_now()
    await session.commit()
    return row


async def update_memory_status(
    session: AsyncSession, *, memory_id: int, status: str
) -> AgentMemory:
    """切换 active/archived（停用后次日计划 prompt 不再注入）。

    Raises:
        NotFoundError: 记忆不存在
    """
    row = await session.get(AgentMemory, memory_id)
    if row is None:
        raise NotFoundError(f"记忆 {memory_id} 不存在")
    row.status = status
    row.updated_at = utc_now()
    await session.commit()
    return row
