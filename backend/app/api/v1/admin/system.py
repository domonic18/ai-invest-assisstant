"""管理后台系统状态 API 端点。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin_user, get_db
from app.schemas.system_status import SystemStatusResponse
from app.services.admin.system_status_service import SystemStatusService

router = APIRouter(dependencies=[Depends(get_current_admin_user)])


@router.get("/status", response_model=SystemStatusResponse)
async def system_status(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SystemStatusResponse:
    """探测 web-api 运行依赖的存储/缓存/搜索/对象存储连通性。"""
    return await SystemStatusService(session).get_status()
