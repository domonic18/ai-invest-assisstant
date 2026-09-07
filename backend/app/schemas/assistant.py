"""对话助手（Agent Protocol）API schemas。

wire 全程对齐 ``@langchain/langgraph-sdk`` 的 camelCase 形状
（``populate_by_name`` 兼容 snake_case 输入）。
"""

from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.base import CamelModel


class ThreadCreateRequest(CamelModel):
    """POST /threads 请求体（langgraph-sdk client.threads.create）。"""

    title: str | None = None
    metadata: dict[str, Any] | None = None
    thread_id: str | None = None


class ThreadResponse(CamelModel):
    thread_id: str
    title: str | None = None
    last_message_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionListResponse(CamelModel):
    sessions: list[ThreadResponse]
    total: int


class RunStreamRequest(CamelModel):
    """POST /threads/{id}/runs/stream 请求体（langgraph-sdk client.runs.stream）。"""

    assistant_id: str | None = None
    input: dict[str, Any] | None = None
    command: dict[str, Any] | None = None
    stream_mode: list[str] | None = None
    config: dict[str, Any] | None = None
    checkpoint: dict[str, Any] | None = None
    on_disconnect: str | None = None
    metadata: dict[str, Any] | None = None


class RunCancelRequest(CamelModel):
    action: str | None = None
    wait: bool | None = None


class ThreadStateResponse(CamelModel):
    """GET /threads/{id}/state 响应（assistant-ui load() 消费）。"""

    values: dict[str, Any] = Field(default_factory=dict)
    next: list[str] = Field(default_factory=list)
    tasks: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SkillSummary(CamelModel):
    id: str
    name: str
    description: str = ""
