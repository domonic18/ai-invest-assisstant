"""AI 分析结果管理（后台通用）API 的 Pydantic schemas。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AdminAiSkillInfo(BaseModel):
    """已纳管 AI skill 清单项（管理页 Tab 与完成事件订阅的数据源）。"""

    skill_id: str
    label: str
    event_type: str | None = None


class AdminAiResultKeyField(BaseModel):
    """业务键的单个字段（如 交易日 / 股票代码 / 行业+版本）。"""

    name: str
    label: str
    value: str


class AdminAiResultItem(BaseModel):
    """AI 结果管理列表行：每个业务键最新一条生成记录的元信息。"""

    id: int
    skill_id: str
    key_fields: list[AdminAiResultKeyField] = []
    model: str | None = None
    latency_ms: int | None = None
    status: str
    created_at: datetime
    history_count: int = 0
    regenerate_prompt: str | None = None


class AdminAiResultDetail(AdminAiResultItem):
    """单条生成记录详情：元信息 + 结构化输出全文。"""

    error_msg: str | None = None
    structured_output: dict[str, Any] | None = None
