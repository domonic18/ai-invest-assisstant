"""MCP 服务配置的 Pydantic schemas。"""

from datetime import datetime

from pydantic import Field

from app.schemas.base import CamelModel


class McpServerCreateRequest(CamelModel):
    """创建 MCP server 配置。"""

    name: str = Field(..., min_length=1, max_length=100)
    transport_type: str = Field("http", pattern=r"^(stdio|http|sse)$")
    command: str | None = Field(None, max_length=500)
    args: list[str] = Field(default_factory=list)
    url: str | None = Field(None, max_length=500)
    env: dict[str, str] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)
    enabled: bool = False
    timeout_seconds: int = Field(30, ge=1, le=300)


class McpServerUpdateRequest(CamelModel):
    """更新 MCP server 配置（None 字段不变）。"""

    name: str | None = Field(None, min_length=1, max_length=100)
    transport_type: str | None = Field(None, pattern=r"^(stdio|http|sse)$")
    command: str | None = Field(None, max_length=500)
    args: list[str] | None = None
    url: str | None = Field(None, max_length=500)
    env: dict[str, str] | None = None
    headers: dict[str, str] | None = None
    enabled: bool | None = None
    timeout_seconds: int | None = Field(None, ge=1, le=300)


class McpServerResponse(CamelModel):
    """MCP server 配置响应（env/headers 仅回显，脱敏由前端展示层控制）。"""

    id: int
    name: str
    transport_type: str
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    url: str | None = None
    env: dict[str, str] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)
    enabled: bool
    timeout_seconds: int
    last_status: str | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class McpToolInfo(CamelModel):
    """连接测试发现的单个工具。"""

    name: str
    description: str | None = None


class McpServerTestResponse(CamelModel):
    """连接测试结果：成功带工具清单，失败带 error。"""

    ok: bool
    tool_count: int = 0
    tools: list[McpToolInfo] = Field(default_factory=list)
    error: str | None = None
