"""新闻、公告与研报的 Pydantic schemas。"""

from datetime import date, datetime
from typing import Any

from pydantic import Field

from app.schemas.base import CamelModel


class NewsDocumentBase(CamelModel):
    """新闻公告的基础字段。"""

    stock_code: str | None = Field(None, max_length=10)
    doc_type: str = Field(..., max_length=20)
    title: str = Field(..., max_length=500)
    summary: str | None = None
    content: str | None = None
    source: str | None = Field(None, max_length=50)
    source_url: str | None = Field(None, max_length=1000)
    publish_date: datetime | None = None
    sentiment: float | None = None
    keywords: list[str] | None = None
    industry_tags: list[str] | None = None
    elasticsearch_doc_id: str | None = Field(None, max_length=50)
    extra: dict[str, Any] = Field(default_factory=dict)


class NewsDocumentCreate(NewsDocumentBase):
    """创建新闻公告的请求 schema。"""


class NewsDocumentUpdate(CamelModel):
    """更新新闻公告的请求 schema。"""

    stock_code: str | None = Field(None, max_length=10)
    doc_type: str | None = Field(None, max_length=20)
    title: str | None = Field(None, max_length=500)
    summary: str | None = None
    content: str | None = None
    source: str | None = Field(None, max_length=50)
    source_url: str | None = Field(None, max_length=1000)
    publish_date: datetime | None = None
    sentiment: float | None = None
    keywords: list[str] | None = None
    industry_tags: list[str] | None = None
    elasticsearch_doc_id: str | None = Field(None, max_length=50)
    extra: dict[str, Any] | None = None


class NewsDocumentResponse(NewsDocumentBase):
    """新闻公告的响应 schema。"""

    id: int
    created_at: datetime


class ResearchReportListRequest(CamelModel):
    """研报列表查询请求 schema。"""

    stock_code: str | None = Field(None, max_length=10)
    q: str | None = Field(None, max_length=100)
    broker: str | None = Field(None, max_length=100)
    industry: str | None = Field(None, max_length=50)
    start_date: date | None = None
    end_date: date | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class ResearchReportResponse(CamelModel):
    """研报列表条目的响应 schema。"""

    id: int
    stock_code: str | None = None
    title: str
    summary: str | None = None
    source: str | None = None
    source_url: str | None = None
    publish_date: datetime | None = None
    sentiment: float | None = None
    keywords: list[str] | None = None
    industry_tags: list[str] | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    broker: str | None = None
    rating: str | None = None
    pages: int | None = None
    industry: str | None = None
    has_summary: bool = False


class ResearchReportFiltersResponse(CamelModel):
    """已采研报的券商/行业去重列表（快筛 badge 数据源）。"""

    brokers: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)


class ResearchReportDetailResponse(ResearchReportResponse):
    """研报详情的响应 schema，包含完整正文。"""

    content: str | None = None
