"""管理后台交易 Agent API 端点（批次 5：配置面；批次 6/9 追加复盘与记忆端点）。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin_user, get_db
from app.schemas.paper_trade import (
    TradingAgentConfigResponse,
    TradingAgentConfigUpdateRequest,
)
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
