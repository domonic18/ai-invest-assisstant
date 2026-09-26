"""管理后台交易 Agent API 端点（批次 5 配置面 + 批次 6 复盘查询 + 批次 7
交易计划查询/人工取消 + agent 自选查询/人工移出 + 记忆管理面）。"""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin_user, get_db
from app.schemas.paper_trade import (
    AgentMemoryResponse,
    AgentMemoryStatusUpdateRequest,
    AgentMemoryUpdateRequest,
    AgentSelectionItem,
    AgentWatchlistGroupResponse,
    TradingAgentConfigResponse,
    TradingAgentConfigUpdateRequest,
    TradingAgentDatesResponse,
    TradingAgentPlanResponse,
    TradingAgentReviewResponse,
)
from app.services.market import trade_calendar_service
from app.services.trading import agent_memory_service, agent_plan_ops, agent_review_service
from app.services.trading.agent_config import get_config_view, update_config

router = APIRouter(
    prefix="/trading-agent",
    dependencies=[Depends(get_current_admin_user)],
)


@router.get("/config", response_model=TradingAgentConfigResponse)
async def get_trading_agent_config(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TradingAgentConfigResponse:
    """读取交易 Agent 配置（LLM 绑定 + 风控阈值 + 自主执行总闸）。"""
    return await get_config_view(session)


@router.put("/config", response_model=TradingAgentConfigResponse)
async def update_trading_agent_config(
    data: TradingAgentConfigUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TradingAgentConfigResponse:
    """保存交易 Agent 配置；llm_config_id 校验存在、启用且用途为 chat。"""
    return await update_config(session, data=data)


@router.get("/review", response_model=TradingAgentReviewResponse)
async def get_trading_agent_review(
    session: Annotated[AsyncSession, Depends(get_db)],
    period: Literal["day", "week", "month"] = Query(..., description="复盘周期"),
    trade_date: date | None = Query(None, description="基准交易日（缺省取该周期最新一条）"),
) -> TradingAgentReviewResponse:
    """读取已生成的模拟盘分层复盘（只读，不触发 LLM）。"""
    content = await agent_review_service.get_review(
        session, period=period, trade_date=trade_date
    )
    if content is None:
        raise agent_review_service.TradingReviewNotFoundError(
            f"{trade_date.isoformat() if trade_date else '最新'} 的 {period} 复盘尚未生成"
        )
    return TradingAgentReviewResponse.model_validate(content.model_dump(mode="json"))


@router.get("/dates", response_model=TradingAgentDatesResponse)
async def get_trading_agent_dates(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TradingAgentDatesResponse:
    """有记录日期清单（日历打点）：已有计划的日期 + 各周期已生成复盘的基准日。"""
    return TradingAgentDatesResponse(
        plan_dates=await agent_plan_ops.list_plan_dates(session),
        review_dates={
            period: await agent_review_service.list_review_dates(session, period=period)
            for period in ("day", "week", "month")
        },
    )


@router.get("/plans", response_model=list[TradingAgentPlanResponse])
async def list_trading_agent_plans(
    session: Annotated[AsyncSession, Depends(get_db)],
    trade_date: date | None = Query(None, description="计划日（缺省取最近交易日）"),
) -> list[TradingAgentPlanResponse]:
    """读取指定日的交易计划（含全部状态，前端按状态分色）。"""
    resolved = trade_date or await trade_calendar_service.resolve_latest_trade_date(
        session
    )
    plans = await agent_plan_ops.list_plans(session, plan_date=resolved)
    return [TradingAgentPlanResponse.model_validate(p) for p in plans]


@router.post("/plans/{plan_id}/cancel", response_model=TradingAgentPlanResponse)
async def cancel_trading_agent_plan(
    plan_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TradingAgentPlanResponse:
    """人工取消当日 active 计划（干预手段之一，triggered 后不可取消）。"""
    plan = await agent_plan_ops.cancel_plan(session, plan_id=plan_id)
    return TradingAgentPlanResponse.model_validate(plan)


@router.get("/selections", response_model=AgentWatchlistGroupResponse | None)
async def get_trading_agent_selections(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AgentWatchlistGroupResponse | None:
    """读取 agent 自选分组（平台级单例；尚未生成选股时返回 null）。"""
    view = await agent_plan_ops.get_agent_group(session)
    if view is None:
        return None
    return AgentWatchlistGroupResponse(
        id=view.group.id,
        name=view.group.name,
        items=[AgentSelectionItem.model_validate(row) for row in view.selections],
    )


@router.delete(
    "/selections/{selection_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_trading_agent_selection(
    selection_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """人工移出 agent 选股（全局生效：当日清单移除，次日不重复选入）。"""
    await agent_plan_ops.remove_selection_manual(session, selection_id=selection_id)


@router.get("/memories", response_model=list[AgentMemoryResponse])
async def list_trading_agent_memories(
    session: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Literal["active", "archived"] | None = Query(
        None, alias="status", description="状态过滤（缺省全部）"
    ),
) -> list[AgentMemoryResponse]:
    """Agent 记忆清单（方法论纪律种子 + 复盘沉淀，按新近度倒序）。"""
    rows = await agent_memory_service.list_memories(session, status=status_filter)
    return [AgentMemoryResponse.model_validate(row) for row in rows]


@router.put("/memories/{memory_id}", response_model=AgentMemoryResponse)
async def update_trading_agent_memory(
    memory_id: int,
    data: AgentMemoryUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AgentMemoryResponse:
    """编辑记忆（标题/正文/类型，未提供字段不变）。"""
    row = await agent_memory_service.update_memory(
        session, memory_id=memory_id, title=data.title, body=data.body, mem_type=data.mem_type
    )
    return AgentMemoryResponse.model_validate(row)


@router.put("/memories/{memory_id}/status", response_model=AgentMemoryResponse)
async def update_trading_agent_memory_status(
    memory_id: int,
    data: AgentMemoryStatusUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AgentMemoryResponse:
    """切换记忆 active/archived（停用后次日计划 prompt 不再注入）。"""
    row = await agent_memory_service.update_memory_status(
        session, memory_id=memory_id, status=data.status
    )
    return AgentMemoryResponse.model_validate(row)
