"""Pydantic schemas for LLM configuration management."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LLMConfigCreate(BaseModel):
    """Request schema for creating an LLM configuration."""

    name: str = Field(..., min_length=1, max_length=100)
    provider: str = Field(..., min_length=1, max_length=20)
    base_url: str = Field(..., min_length=1, max_length=500)
    api_key: str = Field(..., min_length=1)
    model_name: str = Field(..., min_length=1, max_length=100)
    is_default: bool = False
    is_active: bool = True
    extra: dict[str, Any] = Field(default_factory=dict)


class LLMConfigUpdate(BaseModel):
    """Request schema for updating an LLM configuration.

    An empty ``api_key`` means "do not change the stored key".
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
    """Response schema for an LLM configuration (API key is masked)."""

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
    """Response schema for a connectivity test."""

    status: str
    detail: str
    tested_at: datetime
