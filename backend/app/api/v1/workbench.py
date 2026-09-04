"""工作台聚合 API 路由。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.workbench import WorkbenchResponse
from app.services.workbench import workbench_service

router = APIRouter()


@router.get("", response_model=WorkbenchResponse)
async def get_workbench(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> WorkbenchResponse:
    """五模块聚合（日历/复盘/要闻/自选/市场快览），单模块降级返回空态。"""
    return await workbench_service.get_workbench(session, current_user.id)
