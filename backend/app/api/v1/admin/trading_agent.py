"""管理后台交易 Agent API 端点（多 Agent 基座，路径参数 agent_key）。

profile/config 读写 + 复盘/计划/自选/记忆管理面。读端点任意状态可读；
干预类写端点（取消计划/移出自选/记忆编辑）仅 active Agent 可写，
配置保存任意状态可写（未上线/停用的 Agent 也可先配置，D28）。
"""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin_user, get_db
from app.schemas.paper_trade import (
    AgentCapabilityResponse,
    AgentMemoryResponse,
    AgentMemoryStatusUpdateRequest,
    AgentMemoryUpdateRequest,
    AgentOverviewResponse,
    AgentSelectionItem,
    AgentSkillFilesResponse,
    AgentWatchlistGroupResponse,
    TradingAgentCreateRequest,
    TradingAgentDatesResponse,
    TradingAgentPlanResponse,
    TradingAgentPlansResponse,
    TradingAgentProfileResponse,
    TradingAgentProfileUpdateRequest,
    TradingAgentPromptContent,
    TradingAgentPromptTemplate,
    TradingAgentReviewResponse,
)
from app.services.market import trade_calendar_service
from app.services.trading import (
    agent_memory_service,
    agent_overview_service,
    agent_plan_ops,
    agent_registry,
    agent_review_service,
)

router = APIRouter(
    prefix="/trading-agent",
    dependencies=[Depends(get_current_admin_user)],
)


@router.get("/agents", response_model=AgentOverviewResponse)
async def list_trading_agents(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AgentOverviewResponse:
    """全部注册 Agent 的总览聚合（介绍卡 + 计数 + 近期活动 + 下次任务）。"""
    return await agent_overview_service.get_overview(session)


@router.get(
    "/prompt-templates", response_model=list[TradingAgentPromptTemplate]
)
async def list_trading_agent_prompt_templates(
) -> list[TradingAgentPromptTemplate]:
    """可用会话人设模板（prompts/agents/trading_agent_*.yaml 扫描，新建 Agent 下拉）。"""
    return agent_registry.list_prompt_templates()


@router.post(
    "/agents",
    response_model=TradingAgentProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_trading_agent(
    data: TradingAgentCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TradingAgentProfileResponse:
    """新建 Agent（D29：创建即 active 参与调度；技能走共享兜底，绑定账户后才实际下单）。"""
    return await agent_registry.create_agent(session, data=data)


@router.delete("/{agent_key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trading_agent(
    agent_key: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """删除 Agent 并级联清理（解绑模拟盘账户、删计划/选股/记忆/会话，D29）。"""
    await agent_registry.delete_agent(session, agent_key)


@router.get("/{agent_key}/status", response_model=AgentCapabilityResponse)
async def get_trading_agent_status(
    agent_key: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AgentCapabilityResponse:
    """Agent 能力/状态视图（人设/方法论/作业技能/模型/记忆/自动化任务/近期活动）。"""
    return await agent_overview_service.get_agent_status(session, agent_key)


@router.get("/{agent_key}/config", response_model=TradingAgentProfileResponse)
async def get_trading_agent_config(
    agent_key: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TradingAgentProfileResponse:
    """读取单个 Agent 配置（LLM/方法论绑定 + 风控阈值 + 自主执行总闸）。"""
    return await agent_registry.get_agent_view(session, agent_key)


@router.get("/{agent_key}/prompt", response_model=TradingAgentPromptContent)
async def get_trading_agent_prompt(
    agent_key: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TradingAgentPromptContent:
    """会话人设 YAML 原文（配置页只读浏览；prompt_id 经模板白名单校验，D30）。"""
    row = await agent_registry.get_agent(session, agent_key)
    return agent_registry.get_prompt_content(row.prompt_id)


@router.get("/{agent_key}/skill/files", response_model=AgentSkillFilesResponse)
async def get_trading_agent_skill_files(
    agent_key: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AgentSkillFilesResponse:
    """作业技能包文件与方法论基座可视化（配置页只读，D30）。

    trading 技能不进 skill 表（广场不可见），直读镜像 ``skills/<id>/`` 目录。
    """
    return await agent_overview_service.get_agent_skill_files(session, agent_key)


@router.put("/{agent_key}/config", response_model=TradingAgentProfileResponse)
async def update_trading_agent_config(
    agent_key: str,
    data: TradingAgentProfileUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TradingAgentProfileResponse:
    """保存 Agent 信息/配置（任意状态可写，D28）；llm_config_id 校验用途为 chat。"""
    return await agent_registry.update_agent(session, agent_key, data=data)


@router.get("/{agent_key}/review", response_model=TradingAgentReviewResponse)
async def get_trading_agent_review(
    agent_key: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    period: Literal["day", "week", "month"] = Query(..., description="复盘周期"),
    trade_date: date | None = Query(None, description="基准交易日（缺省取该周期最新一条）"),
) -> TradingAgentReviewResponse:
    """读取已生成的模拟盘分层复盘（只读，不触发 LLM）。"""
    content = await agent_review_service.get_review(
        session, agent_key, period=period, trade_date=trade_date
    )
    if content is None:
        raise agent_review_service.TradingReviewNotFoundError(
            f"{trade_date.isoformat() if trade_date else '最新'} 的 {period} 复盘尚未生成"
        )
    return TradingAgentReviewResponse.model_validate(content.model_dump(mode="json"))


@router.get("/{agent_key}/dates", response_model=TradingAgentDatesResponse)
async def get_trading_agent_dates(
    agent_key: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TradingAgentDatesResponse:
    """有记录日期清单（日历打点）：已有计划的日期 + 各周期已生成复盘的基准日。"""
    return TradingAgentDatesResponse(
        plan_dates=await agent_plan_ops.list_plan_dates(session, agent_key),
        review_dates={
            period: await agent_review_service.list_review_dates(
                session, agent_key, period=period
            )
            for period in ("day", "week", "month")
        },
    )


@router.get("/{agent_key}/plans", response_model=TradingAgentPlansResponse)
async def list_trading_agent_plans(
    agent_key: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    trade_date: date | None = Query(None, description="计划日（缺省取最近交易日）"),
) -> TradingAgentPlansResponse:
    """读取指定日的交易计划（含全部状态，前端按状态分色）+ 下一交易日（次日语义）。"""
    resolved = trade_date or await trade_calendar_service.resolve_latest_trade_date(
        session
    )
    return TradingAgentPlansResponse(
        trade_date=resolved,
        next_trade_date=await trade_calendar_service.next_trading_day(session, resolved),
        plans=await agent_plan_ops.list_plan_views(session, agent_key, plan_date=resolved),
    )


@router.post(
    "/{agent_key}/plans/{plan_id}/cancel", response_model=TradingAgentPlanResponse
)
async def cancel_trading_agent_plan(
    agent_key: str,
    plan_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TradingAgentPlanResponse:
    """人工取消当日 active 计划（干预手段之一，triggered 后不可取消）。"""
    plan = await agent_plan_ops.cancel_plan(session, agent_key, plan_id=plan_id)
    return TradingAgentPlanResponse.model_validate(plan)


@router.get("/{agent_key}/selections", response_model=AgentWatchlistGroupResponse | None)
async def get_trading_agent_selections(
    agent_key: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AgentWatchlistGroupResponse | None:
    """读取 agent 自选分组（每 Agent 一组；尚未生成选股时返回 null）。"""
    view = await agent_plan_ops.get_agent_group(session, agent_key)
    if view is None:
        return None
    return AgentWatchlistGroupResponse(
        id=view.group.id,
        name=view.group.name,
        items=[AgentSelectionItem.model_validate(row) for row in view.selections],
    )


@router.delete(
    "/{agent_key}/selections/{selection_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_trading_agent_selection(
    agent_key: str,
    selection_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """人工移出 agent 选股（按 Agent 生效：当日清单移除，次日不重复选入）。"""
    await agent_plan_ops.remove_selection_manual(
        session, agent_key, selection_id=selection_id
    )


@router.get("/{agent_key}/memories", response_model=list[AgentMemoryResponse])
async def list_trading_agent_memories(
    agent_key: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Literal["active", "archived"] | None = Query(
        None, alias="status", description="状态过滤（缺省全部）"
    ),
) -> list[AgentMemoryResponse]:
    """Agent 记忆清单（复盘沉淀 + 手动沉淀，按新近度倒序）。"""
    rows = await agent_memory_service.list_memories(session, agent_key, status=status_filter)
    return [AgentMemoryResponse.model_validate(row) for row in rows]


@router.put("/{agent_key}/memories/{memory_id}", response_model=AgentMemoryResponse)
async def update_trading_agent_memory(
    agent_key: str,
    memory_id: int,
    data: AgentMemoryUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AgentMemoryResponse:
    """编辑记忆（标题/正文/类型，未提供字段不变）。"""
    row = await agent_memory_service.update_memory(
        session,
        agent_key,
        memory_id=memory_id,
        title=data.title,
        body=data.body,
        mem_type=data.mem_type,
    )
    return AgentMemoryResponse.model_validate(row)


@router.put(
    "/{agent_key}/memories/{memory_id}/status", response_model=AgentMemoryResponse
)
async def update_trading_agent_memory_status(
    agent_key: str,
    memory_id: int,
    data: AgentMemoryStatusUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AgentMemoryResponse:
    """切换记忆 active/archived（停用后次日计划 prompt 不再注入）。"""
    row = await agent_memory_service.update_memory_status(
        session, agent_key, memory_id=memory_id, status=data.status
    )
    return AgentMemoryResponse.model_validate(row)
