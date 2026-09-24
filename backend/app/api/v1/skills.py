"""技能广场与用户技能管理 API 路由。"""

from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.skill import (
    CustomSkillCreateRequest,
    CustomSkillUpdateRequest,
    SkillFilesResponse,
    SkillResponse,
    SkillSquareResponse,
    UserSkillResponse,
    UserSkillToggleRequest,
)
from app.schemas.skill_analyze import SkillAnalyzeResponse, SkillArchiveFileInfo
from app.services.skill import SkillService
from app.services.skill.archive_analyzer import ArchiveAnalyzeError, analyze_archive

router = APIRouter()


@router.post("/analyze", response_model=SkillAnalyzeResponse)
async def analyze_skill_archive(
    archive: UploadFile,
    current_user: Annotated[User, Depends(get_current_user)],
) -> SkillAnalyzeResponse:
    """上传技能压缩包（zip/tar.gz），解析 SKILL.md 返回表单预填建议。"""
    data = await archive.read()
    try:
        suggestion = analyze_archive(data)
    except ArchiveAnalyzeError as exc:
        raise BadRequestError(str(exc)) from exc
    return SkillAnalyzeResponse(
        skill_id=suggestion.skill_id,
        label=suggestion.label,
        description=suggestion.description,
        skill_md=suggestion.skill_md,
        system_prompt=suggestion.system_prompt,
        user_prompt_template=suggestion.user_prompt_template,
        sections=suggestion.sections,
        allowed_tools=suggestion.allowed_tools,
        file_index=[
            SkillArchiveFileInfo(path=item["path"], size=item.get("size", 0))
            for item in suggestion.file_index
        ],
    )


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


@router.get("/{skill_id}/files", response_model=SkillFilesResponse)
async def get_skill_files(
    skill_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SkillFilesResponse:
    """技能包文件浏览（builtin 读镜像目录；custom 由配置合成虚拟文件）。"""
    return await SkillService(session).get_skill_files(current_user.id, skill_id)


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


@router.patch("/{skill_id}/install", response_model=UserSkillResponse)
async def toggle_install_skill(
    skill_id: str,
    payload: UserSkillToggleRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserSkillResponse:
    """启用/停用已安装技能（不改安装关系）。"""
    return await SkillService(session).toggle_install_skill(
        current_user.id, skill_id, payload.enabled
    )


@router.delete("/{skill_id}/install", status_code=status.HTTP_204_NO_CONTENT)
async def uninstall_skill(
    skill_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """卸载技能。"""
    await SkillService(session).uninstall_skill(current_user.id, skill_id)
