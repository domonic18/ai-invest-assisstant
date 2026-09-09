"""工作台聚合 API 路由。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.workbench import ReviewStatusResponse, WorkbenchResponse
from app.services.workbench import review_status_service, workbench_service

router = APIRouter()


@router.get("", response_model=WorkbenchResponse)
async def get_workbench(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> WorkbenchResponse:
    """五模块聚合（日历/复盘/要闻/自选/市场快览），单模块降级返回空态。"""
    return await workbench_service.get_workbench(session, current_user.id)


@router.get("/review-status", response_model=ReviewStatusResponse)
async def get_review_status(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ReviewStatusResponse:
    """复盘引擎状态单查（侧边栏复盘状态块，避免拉全量工作台聚合）。"""
    return await review_status_service.get_review_status(session)
