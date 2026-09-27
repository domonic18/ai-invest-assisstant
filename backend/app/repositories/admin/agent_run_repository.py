"""Agent 执行会话仓储（D35 会话管理，只读查询）。"""

from datetime import date

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_run import AgentRun, AgentRunStep
from app.repositories.base import BaseRepository


class AgentRunRepository(BaseRepository[AgentRun]):
    """交易 Agent 执行会话的数据访问。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AgentRun)

    async def list_runs(
        self,
        page: int,
        page_size: int,
        *,
        agent_key: str | None = None,
        kind: str | None = None,
        period: str | None = None,
        status: str | None = None,
        trigger_type: str | None = None,
        trade_date_start: date | None = None,
        trade_date_end: date | None = None,
    ) -> tuple[int, list[AgentRun]]:
        """分页返回执行会话（开始时间倒序，多条件 AND 过滤）。"""
        conditions = []
        if agent_key:
            conditions.append(AgentRun.agent_key == agent_key)
        if kind:
            conditions.append(AgentRun.kind == kind)
        if period:
            conditions.append(AgentRun.period == period)
        if status:
            conditions.append(AgentRun.status == status)
        if trigger_type:
            conditions.append(AgentRun.trigger_type == trigger_type)
        if trade_date_start is not None:
            conditions.append(AgentRun.trade_date >= trade_date_start)
        if trade_date_end is not None:
            conditions.append(AgentRun.trade_date <= trade_date_end)

        count_stmt = select(func.count()).select_from(AgentRun)
        if conditions:
            count_stmt = count_stmt.where(*conditions)
        total: int = (await self.session.execute(count_stmt)).scalar_one()

        stmt = (
            select(AgentRun)
            .order_by(desc(AgentRun.started_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        if conditions:
            stmt = stmt.where(*conditions)
        result = await self.session.execute(stmt)
        return total, list(result.scalars().all())

    async def get_with_steps(
        self, run_id: int
    ) -> tuple[AgentRun, list[AgentRunStep]] | None:
        """返回会话头 + 按 seq 升序的步骤明细；会话不存在返回 None。"""
        run = await self.session.get(AgentRun, run_id)
        if run is None:
            return None
        result = await self.session.execute(
            select(AgentRunStep)
            .where(AgentRunStep.run_id == run_id)
            .order_by(AgentRunStep.seq.asc())
        )
        return run, list(result.scalars().all())
