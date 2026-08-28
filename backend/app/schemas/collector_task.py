"""采集器任务管理的 Pydantic schemas。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CollectorTaskBase(BaseModel):
    """采集器任务的基础字段。"""

    task_name: str = Field(..., max_length=100)
    task_type: str = Field(..., max_length=50)
    source: str = Field(..., max_length=50)
    schedule: str | None = Field(None, max_length=100)
    queue: str | None = Field(None, max_length=20)
    is_active: bool = True


class CollectorTaskCreate(CollectorTaskBase):
    """创建采集器任务的请求 schema。"""


class CollectorTaskUpdate(BaseModel):
    """更新采集器任务的请求 schema。"""

    task_type: str | None = Field(None, max_length=50)
    source: str | None = Field(None, max_length=50)
    schedule: str | None = Field(None, max_length=100)
    queue: str | None = Field(None, max_length=20)
    is_active: bool | None = None


class CollectorTaskResponse(CollectorTaskBase):
    """采集器任务的响应 schema。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    last_run_at: datetime | None = None
    last_status: str
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime
