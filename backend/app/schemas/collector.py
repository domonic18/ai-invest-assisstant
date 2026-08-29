"""采集器管理 API 的 Pydantic schemas。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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


class CollectorTaskCatalogItem(BaseModel):
    """任务目录项（由注册表 TASK_SPECS 派生）。"""

    name: str
    label: str
    data_type: str
    sources: list[str]
    config_params: list[str]
    run_params: list[str]


class CollectorTaskCatalogResponse(BaseModel):
    """任务目录：管理端 UI 触发列表的唯一数据源。"""

    items: list[CollectorTaskCatalogItem]


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
