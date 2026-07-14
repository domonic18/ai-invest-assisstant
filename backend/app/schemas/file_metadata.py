"""Pydantic schemas for file metadata."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class FileMetadataBase(BaseModel):
    """Base fields for file metadata."""

    file_path: str = Field(..., max_length=500)
    original_name: str | None = Field(None, max_length=500)
    file_type: str = Field(..., max_length=20)
    stock_code: str | None = Field(None, max_length=10)
    report_date: date | None = None
    report_type: str | None = Field(None, max_length=20)
    broker: str | None = Field(None, max_length=100)
    file_size: int | None = None
    md5_hash: str | None = Field(None, max_length=32)
    download_url: str | None = None


class FileMetadataCreate(FileMetadataBase):
    """Request schema for creating file metadata."""


class FileMetadataUpdate(BaseModel):
    """Request schema for updating file metadata."""

    original_name: str | None = Field(None, max_length=500)
    file_type: str | None = Field(None, max_length=20)
    stock_code: str | None = Field(None, max_length=10)
    report_date: date | None = None
    report_type: str | None = Field(None, max_length=20)
    broker: str | None = Field(None, max_length=100)
    file_size: int | None = None
    md5_hash: str | None = Field(None, max_length=32)
    download_url: str | None = None


class FileMetadataResponse(FileMetadataBase):
    """Response schema for file metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    download_count: int
    uploaded_at: datetime
