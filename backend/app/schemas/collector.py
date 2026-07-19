"""Pydantic schemas for collector admin APIs."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class CollectorTaskName(str, Enum):
    """Supported collector task names."""

    KLINE = "kline"
    INDEX_KLINE = "index-kline"
    AUCTION = "auction"
    FUND_FLOW = "fund-flow"
    NEWS = "news"
    COMPANY_PROFILE = "company-profile"
    DISCLOSURE = "disclosure"
    SECTOR_FUND_FLOW = "sector-fund-flow"
    DRAGON_LIST = "dragon-list"
    RESEARCH_REPORT = "research-report"
    FINANCIAL_REPORT = "financial-report"
    IPO_INFO = "ipo-info"
    FUND_HOLDINGS = "fund-holdings"
    MACRO = "macro"
    QUOTE = "quote"
    STOCK_LIST = "stock-list"
    LIMIT_UP_POOL = "limit-up-pool"


class CollectorTaskRunRequest(BaseModel):
    """Optional runtime parameters for triggering a collector task."""

    preferred_source: str | None = Field(None, max_length=50)
    symbols: list[str] | None = Field(None, max_length=100)
    period: str | None = Field(None, max_length=20)
    start_date: str | None = Field(None, max_length=20)
    end_date: str | None = Field(None, max_length=20)
    sector_type: str | None = Field(None, max_length=20)
    indicators: list[str] | None = Field(None, max_length=20)
    report_types: list[str] | None = Field(None, max_length=20)
    report_date: str | None = Field(None, max_length=20)
    trade_date: str | None = Field(None, max_length=20)


class CollectorTaskChannelItem(BaseModel):
    """A single channel available for a task."""

    source: str
    name: str
    is_enabled: bool


class CollectorTaskChannelsResponse(BaseModel):
    """Available channels and resolved default for a collector task."""

    task_name: str
    data_type: str
    channels: list[CollectorTaskChannelItem]
    resolved_source: str | None


class CollectorRunResponse(BaseModel):
    """Response returned after accepting a collector trigger request."""

    task_name: str
    status: str = "accepted"
    log_id: int | None = None


class CollectorLogResponse(BaseModel):
    """A single collector execution log entry."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    task_name: str
    source: str | None
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    records_count: int
    error_msg: str | None
    metadata: dict | None = Field(alias="meta")
