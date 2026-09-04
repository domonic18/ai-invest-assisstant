"""助手 Skill 列表端点。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.assistant import SkillSummary
from app.services.assistant.assistant_service import AssistantService

router = APIRouter()


@router.get("/skills", response_model=list[SkillSummary])
async def list_skills(
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[SkillSummary]:
    """可用 Skill 摘要（frontmatter name/description）。"""
    return AssistantService(session).list_skills()
