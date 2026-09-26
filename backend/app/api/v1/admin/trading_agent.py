"""管理后台交易 Agent API 端点（批次 5 配置面 + 批次 6 复盘查询 + 批次 7
交易计划查询/人工取消；批次 9 追加记忆端点）。"""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin_user, get_db
from app.schemas.paper_trade import (
    TradingAgentConfigResponse,
    TradingAgentConfigUpdateRequest,
    TradingAgentPlanResponse,
    TradingAgentReviewResponse,
)
from app.services.market import trade_calendar_service
from app.services.trading import agent_plan_ops, agent_review_service
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
