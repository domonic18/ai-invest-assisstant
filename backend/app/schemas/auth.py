"""认证相关的 Pydantic schemas。"""

from pydantic import EmailStr, Field

from app.schemas.base import CamelModel
from app.schemas.user import UserResponse


class TokenPayload(CamelModel):
    """JWT payload。"""

    sub: str | None = None
    role: str | None = None


class RegisterRequest(CamelModel):
    """用户注册（申请）请求。"""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    application_note: str | None = Field(None, max_length=500, description="申请说明（可选）")


class RegisterAccepted(CamelModel):
    """注册申请受理回执（不发登录凭证，审批通过后方可登录）。"""

    message: str = "注册申请已提交，请等待管理员审批通过后登录"


class AuthResponse(CamelModel):
    """认证响应。"""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse
