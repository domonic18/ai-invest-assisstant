"""认证 API 路由。"""

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token
from app.dependencies import get_db
from app.schemas.auth import AuthResponse, RegisterRequest
from app.schemas.user import UserResponse
from app.services.user import UserService

router = APIRouter()
settings = get_settings()


@router.post("/register", response_model=AuthResponse)
async def register(data: RegisterRequest, session: AsyncSession = Depends(get_db)) -> AuthResponse:
    """用户注册。"""
    user_service = UserService(session)
    if await user_service.get_user_by_username(data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )
    if await user_service.get_user_by_email(data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = await user_service.create_user(data)
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role},
        expires_delta=timedelta(minutes=settings.jwt_access_token_expire_minutes),
    )
    return AuthResponse(access_token=access_token, user=UserResponse.model_validate(user))


@router.post("/login", response_model=AuthResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """用户登录。"""
    user_service = UserService(session)
    user = await user_service.authenticate_user(form_data.username, form_data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    await user_service.update_last_login(user)
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role},
        expires_delta=timedelta(minutes=settings.jwt_access_token_expire_minutes),
    )
    return AuthResponse(access_token=access_token, user=UserResponse.model_validate(user))


@router.post("/wx-login")
async def wx_login() -> dict[str, Any]:
    """微信登录（占位实现，需小程序 appid/secret 联调）。"""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="WeChat login is not implemented yet",
    )
