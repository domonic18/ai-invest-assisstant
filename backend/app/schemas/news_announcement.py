"""Pydantic schemas for news announcements and research reports."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NewsAnnouncementBase(BaseModel):
    """Base fields for news announcement."""

    stock_code: str | None = Field(None, max_length=10)
    doc_type: str = Field(..., max_length=20)
    title: str = Field(..., max_length=500)
    summary: str | None = None
    content: str | None = None
    source: str | None = Field(None, max_length=50)
    source_url: str | None = Field(None, max_length=1000)
    publish_date: datetime | None = None
    sentiment: Decimal | None = None
    keywords: list[str] | None = None
    industry_tags: list[str] | None = None
    es_id: str | None = Field(None, max_length=50)
    extra: dict[str, Any] = Field(default_factory=dict)


class NewsAnnouncementCreate(NewsAnnouncementBase):
    """Request schema for creating a news announcement."""


class NewsAnnouncementUpdate(BaseModel):
    """Request schema for updating a news announcement."""

    stock_code: str | None = Field(None, max_length=10)
    doc_type: str | None = Field(None, max_length=20)
    title: str | None = Field(None, max_length=500)
    summary: str | None = None
    content: str | None = None
    source: str | None = Field(None, max_length=50)
    source_url: str | None = Field(None, max_length=1000)
    publish_date: datetime | None = None
    sentiment: Decimal | None = None
    keywords: list[str] | None = None
    industry_tags: list[str] | None = None
    es_id: str | None = Field(None, max_length=50)
    extra: dict[str, Any] | None = None


class NewsAnnouncementResponse(NewsAnnouncementBase):
    """Response schema for a news announcement."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class ResearchReportListRequest(BaseModel):
    """Request schema for listing research reports."""

    stock_code: str | None = Field(None, max_length=10)
    q: str | None = Field(None, max_length=100)
    start_date: date | None = None
    end_date: date | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
