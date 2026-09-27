"""管理后台 Agent 会话管理 API（D35：执行轨迹列表 + 详情时间线）。

自动化任务（每日计划/分层复盘）执行会话的观测面：列表按 Agent/类型/
周期/状态/触发方式/基准日快速筛选；详情返回步骤明细（输入组装/KB 检索/
LLM 全文/校验/落库）。只读端点，观测写入由服务层 recorder 完成。
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.pagination import DEFAULT_PAGE, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.dependencies import get_current_admin_user, get_db
from app.repositories.admin.agent_run_repository import AgentRunRepository
from app.schemas.agent_run import (
    AgentRunDetailResponse,
    AgentRunListResponse,
    AgentRunResponse,
    AgentRunStepResponse,
)

router = APIRouter(dependencies=[Depends(get_current_admin_user)])


@router.get("/agent-runs", response_model=AgentRunListResponse)
async def list_agent_runs(
    session: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(DEFAULT_PAGE, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    agent_key: str | None = Query(None),
    kind: str | None = Query(None),
    period: str | None = Query(None),
    status: str | None = Query(None),
    trigger_type: str | None = Query(None),
    trade_date_start: date | None = Query(None),
    trade_date_end: date | None = Query(None),
) -> AgentRunListResponse:
    """分页返回执行会话（started_at 倒序，条件任传）。"""
    total, rows = await AgentRunRepository(session).list_runs(
        page,
        page_size,
        agent_key=agent_key,
        kind=kind,
        period=period,
        status=status,
        trigger_type=trigger_type,
        trade_date_start=trade_date_start,
        trade_date_end=trade_date_end,
    )
    return AgentRunListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[AgentRunResponse.model_validate(row) for row in rows],
    )


@router.get("/agent-runs/{run_id}", response_model=AgentRunDetailResponse)
async def get_agent_run(
    run_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AgentRunDetailResponse:
    """返回会话详情（头部 + seq 升序步骤时间线）。"""
    from app.core.exceptions import NotFoundError

    found = await AgentRunRepository(session).get_with_steps(run_id)
    if found is None:
        raise NotFoundError(f"会话 {run_id} 不存在")
    run, steps = found
    detail = AgentRunDetailResponse(
        **AgentRunResponse.model_validate(run).model_dump(),
        steps=[AgentRunStepResponse.model_validate(step) for step in steps],
    )
    return detail
