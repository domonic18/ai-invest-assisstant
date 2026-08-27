"""Pydantic schemas for collector task management."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CollectorTaskBase(BaseModel):
    """Base fields for collector task."""

    task_name: str = Field(..., max_length=100)
    task_type: str = Field(..., max_length=50)
    source: str = Field(..., max_length=50)
    schedule: str | None = Field(None, max_length=100)
    queue: str | None = Field(None, max_length=20)
    is_active: bool = True


class CollectorTaskCreate(CollectorTaskBase):
    """Request schema for creating a collector task."""


class CollectorTaskUpdate(BaseModel):
    """Request schema for updating a collector task."""

    task_type: str | None = Field(None, max_length=50)
    source: str | None = Field(None, max_length=50)
    schedule: str | None = Field(None, max_length=100)
    queue: str | None = Field(None, max_length=20)
    is_active: bool | None = None


class CollectorTaskResponse(CollectorTaskBase):
    """Response schema for a collector task."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    last_run_at: datetime | None = None
    last_status: str
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime
