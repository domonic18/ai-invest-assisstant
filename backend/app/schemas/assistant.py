"""对话助手（Agent Protocol）API schemas。

线程/运行相关 schema 的 wire 全程对齐 ``@langchain/langgraph-sdk``
的 **snake_case** 形状（LangGraph Platform 官方契约，如 ``thread_id``/
``stream_mode``/``on_disconnect``），勿改用 CamelModel——SDK Client
原样透传 JSON，camelCase 会导致前端读不到 ``thread_id``。
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.base import CamelModel


class ThreadCreateRequest(BaseModel):
    """POST /threads 请求体（langgraph-sdk client.threads.create）。"""

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

    assistant_id: str | None = None
    input: dict[str, Any] | None = None
    command: dict[str, Any] | None = None
    stream_mode: list[str] | None = None
    config: dict[str, Any] | None = None
    checkpoint: dict[str, Any] | None = None
    on_disconnect: str | None = None
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


class SkillSummary(CamelModel):
    """技能摘要（旧字段不变，kind/isCustom 为批次7 增量，wire 向后兼容）。"""

    id: str
    name: str
    description: str = ""
    kind: str | None = None
    is_custom: bool = False
