"""Authentication related Pydantic schemas."""

from pydantic import BaseModel, EmailStr, Field

from app.schemas.user import UserResponse


class TokenPayload(BaseModel):
    """JWT payload。"""

    sub: str | None = None
    role: str | None = None


class RegisterRequest(BaseModel):
    """用户注册请求。"""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class AuthResponse(BaseModel):
    """认证响应。"""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse
