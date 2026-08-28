"""采集器管理 API 的 Pydantic schemas。"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class CollectorTaskName(str, Enum):
    """支持的采集器任务名。"""

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
    """触发采集器任务的可选运行参数。"""

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
    """任务可用的单个渠道。"""

    source: str
    name: str
    is_enabled: bool


class CollectorTaskChannelsResponse(BaseModel):
    """采集器任务的可用渠道及解析出的默认渠道。"""

    task_name: str
    data_type: str
    channels: list[CollectorTaskChannelItem]
    resolved_source: str | None


class CollectorRunResponse(BaseModel):
    """接受采集触发请求后返回的响应。"""

    task_name: str
    status: str = "accepted"
    log_id: int | None = None
    celery_task_id: str | None = None


class CollectorLogResponse(BaseModel):
    """单条采集器执行日志。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    task_name: str
    source: str | None
    status: str
    celery_task_id: str | None = None
    started_at: datetime | None
    finished_at: datetime | None
    records_count: int
    error_msg: str | None
    metadata: dict | None = Field(alias="meta")


class CollectorDeadLetterResponse(BaseModel):
    """单条采集器死信记录。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    task_name: str
    source: str | None
    payload: dict
    celery_task_id: str | None
    collector_log_id: int | None
    error_msg: str | None
    retry_count: int
    created_at: datetime
