"""LLM 配置管理的 Pydantic schemas。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LLMConfigCreate(BaseModel):
    """创建 LLM 配置的请求 schema。"""

    name: str = Field(..., min_length=1, max_length=100)
    provider: str = Field(..., min_length=1, max_length=20)
    base_url: str = Field(..., min_length=1, max_length=500)
    api_key: str = Field(..., min_length=1)
    model_name: str = Field(..., min_length=1, max_length=100)
    is_default: bool = False
    is_active: bool = True
    extra: dict[str, Any] = Field(default_factory=dict)


class LLMConfigUpdate(BaseModel):
    """更新 LLM 配置的请求 schema。

    空 ``api_key`` 表示不修改已存储的 key。
    """

    name: str | None = Field(None, min_length=1, max_length=100)
    provider: str | None = Field(None, min_length=1, max_length=20)
    base_url: str | None = Field(None, min_length=1, max_length=500)
    api_key: str | None = Field(None, min_length=1)
    model_name: str | None = Field(None, min_length=1, max_length=100)
    is_default: bool | None = None
    is_active: bool | None = None
    extra: dict[str, Any] | None = None


class LLMConfigResponse(BaseModel):
    """LLM 配置的响应 schema（API key 已脱敏）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    provider: str
    base_url: str
    model_name: str
    api_key_masked: str
    is_default: bool
    is_active: bool
    extra: dict[str, Any]
    last_tested_at: datetime | None
    last_test_status: str | None
    last_test_error: str | None
    created_at: datetime
    updated_at: datetime


class LLMConfigTestResponse(BaseModel):
    """连通性测试的响应 schema。"""

    status: str
    detail: str
    tested_at: datetime
