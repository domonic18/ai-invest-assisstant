"""对话助手（Agent Protocol）API schemas。

请求体字段对齐 ``@langchain/langgraph-sdk`` 的 camelCase wire 形状
（alias 兼容 snake_case），响应保持项目统一的 snake_case。
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ThreadCreateRequest(BaseModel):
    """POST /threads 请求体（langgraph-sdk client.threads.create）。"""

    model_config = ConfigDict(populate_by_name=True)

    title: str | None = None
    metadata: dict[str, Any] | None = None
    thread_id: str | None = None


class ThreadResponse(BaseModel):
    thread_id: str
    title: str | None = None
    last_message_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionListResponse(BaseModel):
    sessions: list[ThreadResponse]
    total: int


class RunStreamRequest(BaseModel):
    """POST /threads/{id}/runs/stream 请求体（langgraph-sdk client.runs.stream）。"""

    model_config = ConfigDict(populate_by_name=True)

    assistant_id: str | None = Field(default=None, alias="assistantId")
    input: dict[str, Any] | None = None
    command: dict[str, Any] | None = None
    stream_mode: list[str] | None = Field(default=None, alias="streamMode")
    config: dict[str, Any] | None = None
    checkpoint: dict[str, Any] | None = None
    on_disconnect: str | None = Field(default=None, alias="onDisconnect")
    metadata: dict[str, Any] | None = None


class RunCancelRequest(BaseModel):
    action: str | None = None
    wait: bool | None = None


class ThreadStateResponse(BaseModel):
    """GET /threads/{id}/state 响应（assistant-ui load() 消费）。"""

    values: dict[str, Any] = Field(default_factory=dict)
    next: list[str] = Field(default_factory=list)
    tasks: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SkillSummary(BaseModel):
    id: str
    name: str
    description: str = ""
