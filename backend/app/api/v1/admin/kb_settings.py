"""管理后台知识库设置 API 端点（F-KB：域参数 + 模型角色槽位）。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin_user, get_db
from app.models.user import User
from app.schemas.kb import KbSettingsResponse, KbSettingsUpdateRequest
from app.services.kb.settings_service import get_settings_view, update_settings

router = APIRouter(
    prefix="/kb/settings",
    dependencies=[Depends(get_current_admin_user)],
)


@router.get("", response_model=KbSettingsResponse)
async def get_kb_settings(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> KbSettingsResponse:
    """读取知识库设置（脱敏视图）。"""
    return await get_settings_view(session)


@router.put("", response_model=KbSettingsResponse)
async def update_kb_settings(
    data: KbSettingsUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin_user)],
) -> KbSettingsResponse:
    """保存知识库设置；模型角色槽位逐项校验 purpose 匹配。"""
    return await update_settings(session, admin_id=admin.id, data=data)
