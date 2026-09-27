"""Agent 执行会话管理 schema（D35 会话管理，camelCase wire）。

列表行 + 详情（含步骤时间线）。payload 为步骤完整输入输出（代码层已按
8KB/段截断，prompt/结构化输出 64KB），结构由 step_key 决定，前端按需渲染。
"""

from datetime import date, datetime
from typing import Any

from app.schemas.base import CamelModel


class AgentRunResponse(CamelModel):
    """执行会话行（列表与详情头部共用）。"""

    id: int
    agent_key: str
    kind: str
    period: str | None = None
    trigger_type: str
    trade_date: date | None = None
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: int | None = None
    error_msg: str | None = None
    summary: dict[str, Any] | None = None
    collector_log_id: int | None = None


class AgentRunStepResponse(CamelModel):
    """执行步骤明细（聊天式时间线节点）。"""

    seq: int
    step_key: str
    title: str | None = None
    status: str
    started_at: datetime | None = None
    duration_ms: int | None = None
    payload: dict[str, Any] | None = None


class AgentRunDetailResponse(AgentRunResponse):
    """会话详情：头部 + 按 seq 升序的步骤时间线。"""

    steps: list[AgentRunStepResponse] = []


class AgentRunListResponse(CamelModel):
    """会话列表分页响应（started_at 倒序）。"""

    total: int
    page: int
    page_size: int
    items: list[AgentRunResponse]
