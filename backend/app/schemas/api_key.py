"""MCP API Key 的 Pydantic schemas（wire camelCase）。"""

from datetime import datetime

from pydantic import Field, field_validator

from app.core.constants import API_KEY_SCOPES
from app.schemas.base import CamelModel


class ApiKeyCreateRequest(CamelModel):
    """管理员签发 API Key。"""

    user_id: int = Field(..., ge=1)
    name: str = Field(..., min_length=1, max_length=100)
    scopes: list[str] = Field(..., min_length=1)
    expires_at: datetime | None = None

    @field_validator("scopes")
    @classmethod
    def _validate_scopes(cls, value: list[str]) -> list[str]:
        unknown = sorted(set(value) - set(API_KEY_SCOPES))
        if unknown:
            raise ValueError(f"未知权限范围：{'、'.join(unknown)}")
        return list(dict.fromkeys(value))


class ApiKeySelfCreateRequest(CamelModel):
    """个人设置自助签发：scope 由服务端固定，用户只决定名称与有效期。"""

    name: str = Field(..., min_length=1, max_length=100)
    expires_at: datetime | None = None


class ApiKeyResponse(CamelModel):
    """API Key 列表行（不含哈希与明文）。"""

    id: int
    user_id: int
    username: str | None = None
    name: str
    key_prefix: str
    scopes: list[str]
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None
    created_at: datetime


class ApiKeyIssuedResponse(ApiKeyResponse):
    """签发响应：明文 token 仅此一次返回。"""

    token: str
    note: str = "请立即保存该 Token，服务端只存哈希，无法再次查看明文。"
