"""个人设置的 MCP API Key 自助管理端点（仅操作本人 Key）。

与管理员端点 ``/admin/api-keys`` 的差异：用户身份取当前登录用户，
不可指定 ``user_id``；scope 由服务端按已上线能力固定下发。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import API_KEY_SELF_SERVICE_SCOPES
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.api_key import (
    ApiKeyIssuedResponse,
    ApiKeyResponse,
    ApiKeySelfCreateRequest,
)
from app.services.user.api_key_service import ApiKeyService

router = APIRouter()


@router.get("/", response_model=list[ApiKeyResponse])
async def list_my_api_keys(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[ApiKeyResponse]:
    """当前用户的 API Key 列表（不含哈希与明文）。"""
    return await ApiKeyService(session).list_keys(current_user.id)


@router.post(
    "/",
    response_model=ApiKeyIssuedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_my_api_key(
    payload: ApiKeySelfCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ApiKeyIssuedResponse:
    """为自己签发 API Key（明文 token 仅本次响应返回）。"""
    return await ApiKeyService(session).create_key(
        user_id=current_user.id,
        name=payload.name,
        scopes=list(API_KEY_SELF_SERVICE_SCOPES),
        expires_at=payload.expires_at,
    )


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_my_api_key(
    key_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """吊销自己的 API Key（幂等，他人 Key 返回 404）。"""
    await ApiKeyService(session).revoke_own_key(key_id, current_user.id)
