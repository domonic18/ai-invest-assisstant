"""管理后台 MCP API Key 管理端点（签发 / 列表 / 吊销）。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin_user, get_db
from app.schemas.api_key import (
    ApiKeyCreateRequest,
    ApiKeyIssuedResponse,
    ApiKeyResponse,
)
from app.services.user.api_key_service import ApiKeyService

router = APIRouter(dependencies=[Depends(get_current_admin_user)])


@router.get("/", response_model=list[ApiKeyResponse])
async def list_api_keys(
    session: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[int | None, Query(ge=1)] = None,
) -> list[ApiKeyResponse]:
    """全部 API Key（可按用户过滤；不回显哈希与明文）。"""
    return await ApiKeyService(session).list_keys(user_id)


@router.post(
    "/",
    response_model=ApiKeyIssuedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_api_key(
    payload: ApiKeyCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ApiKeyIssuedResponse:
    """签发 API Key（明文 token 仅本次响应返回）。"""
    return await ApiKeyService(session).create_key(
        user_id=payload.user_id,
        name=payload.name,
        scopes=payload.scopes,
        expires_at=payload.expires_at,
    )


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """吊销 API Key（幂等）。"""
    await ApiKeyService(session).revoke_key(key_id)
