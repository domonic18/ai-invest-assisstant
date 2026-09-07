"""技能广场与用户技能管理 API 路由。"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.skill import (
    CustomSkillCreateRequest,
    CustomSkillUpdateRequest,
    SkillResponse,
    SkillSquareResponse,
    UserSkillResponse,
)
from app.services.skill import SkillService

router = APIRouter()


@router.get("", response_model=SkillSquareResponse)
async def list_skills(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SkillSquareResponse:
    """技能广场（可安装）+ 我的技能（已安装 + 本人 custom）。"""
    return await SkillService(session).list_skills(current_user.id)


@router.post(
    "",
    response_model=SkillResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_custom_skill(
    payload: CustomSkillCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SkillResponse:
    """创建 custom skill（draft 态）。"""
    return await SkillService(session).create_custom_skill(current_user.id, payload)


@router.get("/{skill_id}", response_model=SkillResponse)
async def get_skill_detail(
    skill_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SkillResponse:
    """技能详情（未发布仅属主可见）。"""
    return await SkillService(session).get_skill_detail(current_user.id, skill_id)


@router.patch("/{skill_id}", response_model=SkillResponse)
async def update_custom_skill(
    skill_id: str,
    payload: CustomSkillUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SkillResponse:
    """更新本人 custom skill。"""
    return await SkillService(session).update_custom_skill(
        current_user.id, skill_id, payload
    )


@router.post("/{skill_id}/publish", response_model=SkillResponse)
async def publish_custom_skill(
    skill_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SkillResponse:
    """发布本人 custom skill（幂等）。"""
    return await SkillService(session).publish_custom_skill(current_user.id, skill_id)


@router.post(
    "/{skill_id}/install",
    response_model=UserSkillResponse,
    status_code=status.HTTP_201_CREATED,
)
async def install_skill(
    skill_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserSkillResponse:
    """安装技能。"""
    return await SkillService(session).install_skill(current_user.id, skill_id)


@router.delete("/{skill_id}/install", status_code=status.HTTP_204_NO_CONTENT)
async def uninstall_skill(
    skill_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """卸载技能。"""
    await SkillService(session).uninstall_skill(current_user.id, skill_id)
