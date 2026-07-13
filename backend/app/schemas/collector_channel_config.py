"""Pydantic schemas for collector channel configuration management."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CollectorChannelConfigCreate(BaseModel):
    """Request schema for creating a collector channel configuration."""

    source: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    base_url: str | None = Field(None, max_length=500)
    api_key: str | None = Field(None, min_length=1)
    is_enabled: bool = True
    supported_data_types: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)


class CollectorChannelConfigUpdate(BaseModel):
    """Request schema for updating a collector channel configuration.

    An empty ``api_key`` means "do not change the stored key".
    """

    name: str | None = Field(None, min_length=1, max_length=100)
    base_url: str | None = Field(None, max_length=500)
    api_key: str | None = Field(None, min_length=1)
    is_enabled: bool | None = None
    supported_data_types: list[str] | None = None
    extra: dict[str, Any] | None = None


class CollectorChannelConfigResponse(BaseModel):
    """Response schema for a collector channel configuration (API key is masked)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    name: str
    base_url: str | None
    api_key_masked: str | None
    is_enabled: bool
    supported_data_types: list[str]
    extra: dict[str, Any]
    created_at: datetime
    updated_at: datetime
