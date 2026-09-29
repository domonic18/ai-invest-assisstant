"""交易 Agent 记忆管理服务（plan §12.3：查看 / 编辑 / 停用；多 Agent D23）。

记忆是 Agent 私有资产（不经 KB）：status='active' 条目由每日计划生成服务
注入 prompt（``agent_plan_input._active_memories``）；停用 = archived
（不物理删除，保留归因链路）。批次 9 起复盘 experiences 自动沉淀
（``sediment_experiences``，同标题去重 + 刷时间）与手动沉淀（POST）双路接入。
查询按 agent_key 维度过滤。
"""

from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_now
from app.core.exceptions import NotFoundError
from app.models.agent_trading import AgentMemory

if TYPE_CHECKING:
    from app.services.trading.agent_review_content import ReviewExperience


async def list_memories(
    session: AsyncSession, agent_key: str, *, status: str | None = None
) -> list[AgentMemory]:
    """指定 Agent 的记忆清单（缺省全部状态，按新近度倒序）。"""
    stmt = select(AgentMemory).where(AgentMemory.agent_key == agent_key)
    if status is not None:
        stmt = stmt.where(AgentMemory.status == status)
    stmt = stmt.order_by(AgentMemory.updated_at.desc())
    rows = await session.execute(stmt)
    return list(rows.scalars().all())


async def create_memory(
    session: AsyncSession,
    agent_key: str,
    *,
    title: str,
    body: str,
    mem_type: str,
) -> AgentMemory:
    """手动沉淀一条记忆（source='manual'，立即 active 参与次日计划注入）。

    Raises:
        NotFoundError: agent_key 未注册。
    """
    from app.services.trading import agent_registry

    await agent_registry.get_agent(session, agent_key)
    row = AgentMemory(
        agent_key=agent_key,
        mem_type=mem_type,
        title=title,
        body=body,
        source="manual",
        status="active",
        source_result_id=None,
    )
    session.add(row)
    await session.commit()
    return row


async def sediment_experiences(
    session: AsyncSession,
    agent_key: str,
    *,
    experiences: list["ReviewExperience"],
    source_result_id: int,
) -> int:
    """复盘 experiences 幂等沉淀（批次 9）：同标题去重 + 刷时间。

    partial unique ``(agent_key, title) WHERE source='auto'`` 只约束自动沉淀
    行；冲突走 DO UPDATE 仅刷 ``updated_at``（每日计划注入 top20 按其倒序，
    重复教训自动浮头强化），body 不覆盖以保留人工编辑。不 commit——由调用方
    （复盘服务）与 ai_analysis_result 缓存行同一事务原子提交。

    Returns:
        受影响行数（插入 + 冲突刷新合计，记 agent_run summary 用）。
    """
    rows = [
        {
            "agent_key": agent_key,
            "mem_type": item.mem_type,
            "title": item.title.strip()[:128],
            "body": item.body,
            "source": "auto",
            "status": "active",
            "source_result_id": source_result_id,
        }
        for item in experiences
        if item.title.strip() and item.body.strip()
    ]
    if not rows:
        return 0
    stmt = (
        pg_insert(AgentMemory)
        .values(rows)
        .on_conflict_do_update(
            index_elements=[AgentMemory.agent_key, AgentMemory.title],
            index_where=AgentMemory.source == "auto",
            set_={AgentMemory.updated_at: func.now()},
        )
    )
    result = await session.execute(stmt)
    return int(getattr(result, "rowcount", 0) or 0)


async def update_memory(
    session: AsyncSession,
    agent_key: str,
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
    if row is None or row.agent_key != agent_key:
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


async def delete_memory(
    session: AsyncSession, agent_key: str, *, memory_id: int
) -> None:
    """物理删除一条记忆（管理面手动清理；复盘同标题经验下次沉淀会重新生成）。

    Raises:
        NotFoundError: 记忆不存在
    """
    row = await session.get(AgentMemory, memory_id)
    if row is None or row.agent_key != agent_key:
        raise NotFoundError(f"记忆 {memory_id} 不存在")
    await session.delete(row)
    await session.commit()


async def update_memory_status(
    session: AsyncSession, agent_key: str, *, memory_id: int, status: str
) -> AgentMemory:
    """切换 active/archived（停用后次日计划 prompt 不再注入）。

    Raises:
        NotFoundError: 记忆不存在
    """
    row = await session.get(AgentMemory, memory_id)
    if row is None or row.agent_key != agent_key:
        raise NotFoundError(f"记忆 {memory_id} 不存在")
    row.status = status
    row.updated_at = utc_now()
    await session.commit()
    return row
