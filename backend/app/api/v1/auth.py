"""认证 API 路由。"""

from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.security import create_access_token
from app.dependencies import get_db
from app.schemas.auth import AuthResponse, RegisterAccepted, RegisterRequest
from app.schemas.user import UserResponse
from app.services.user import UserService
from app.services.user.register_service import RegisterService

router = APIRouter()
settings = get_settings()


@router.post(
    "/register", response_model=RegisterAccepted, status_code=status.HTTP_201_CREATED
)
async def register(
    data: RegisterRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RegisterAccepted:
    """提交注册申请：受理后待管理员审批，不签发登录凭证（arch/10 §6）。"""
    client_ip = request.client.host if request.client else "-"
    return await RegisterService(session).submit(data, client_ip)


@router.post("/login", response_model=AuthResponse)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """用户登录（防爆破限流、审批状态拦截与失败审计在服务层）。"""
    user_service = UserService(session)
    client_ip = request.client.host if request.client else "-"
    user = await user_service.attempt_login(form_data.username, form_data.password, client_ip)

    await user_service.update_last_login(user)
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role},
        expires_delta=timedelta(minutes=settings.jwt_access_token_expire_minutes),
    )
    return AuthResponse(access_token=access_token, user=UserResponse.model_validate(user))


@router.post("/wx-login")
async def wx_login() -> dict[str, Any]:
    """微信登录（占位实现，需小程序 appid/secret 联调）。"""
    raise AppError("WeChat login is not implemented yet", status_code=501)
