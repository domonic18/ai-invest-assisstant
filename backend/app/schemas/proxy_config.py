"""代理服务器配置管理的 Pydantic schemas。"""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.base import CamelModel


class ProxyConfigCreate(CamelModel):
    """创建代理服务器配置的请求 schema。"""

    name: str = Field(..., min_length=1, max_length=128)
    protocol: Literal["http", "socks5"] = "http"
    host: str = Field(..., min_length=1, max_length=255)
    port: int = Field(..., ge=1, le=65535)
    username: str | None = Field(None, max_length=255)
    password: str | None = Field(None, min_length=1, max_length=255)
    is_enabled: bool = True


class ProxyConfigUpdate(CamelModel):
    """更新代理服务器配置的请求 schema。

    空 ``password`` 表示不修改已存储的密码。
    """

    name: str | None = Field(None, min_length=1, max_length=128)
    protocol: Literal["http", "socks5"] | None = None
    host: str | None = Field(None, min_length=1, max_length=255)
    port: int | None = Field(None, ge=1, le=65535)
    username: str | None = Field(None, max_length=255)
    password: str | None = Field(None, min_length=1, max_length=255)
    is_enabled: bool | None = None


class ProxyConfigResponse(CamelModel):
    """代理服务器配置的响应 schema（密码已脱敏）。"""

    id: int
    name: str
    protocol: str
    host: str
    port: int
    username: str | None
    password_masked: str | None
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


class ProxyConfigTestResponse(CamelModel):
    """代理连通性测试的响应 schema。"""

    ok: bool
    status_code: int | None
    latency_ms: int
    error: str | None
