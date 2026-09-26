"""管理后台交易 Agent API 端点（批次 5 配置面 + 批次 6 复盘查询；批次 9 追加记忆端点）。"""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin_user, get_db
from app.schemas.paper_trade import (
    TradingAgentConfigResponse,
    TradingAgentConfigUpdateRequest,
    TradingAgentReviewResponse,
)
from app.services.trading import agent_review_service
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
