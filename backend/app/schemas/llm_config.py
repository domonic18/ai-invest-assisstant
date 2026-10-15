"""LLM 配置管理的 Pydantic schemas。"""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.schemas.base import CamelModel

LLMProtocol = Literal["openai", "anthropic", "systemone"]

#: 配置用途（F-KB 模型角色槽位按 purpose 过滤候选：clean/extract=chat、vision=vision、
#: embedding=embedding）。``decision`` 为判断模型（System One，D23）——不进任何
#: F-KB 槽位候选，也不参与默认对话解析（仓储层 get_default_active 按 purpose 过滤）
LLMPurpose = Literal["chat", "embedding", "vision", "decision"]


class LLMConfigCreate(CamelModel):
    """创建 LLM 配置的请求 schema。

    ``protocol`` 缺省时按 ``provider`` 推断：anthropic 渠道 → anthropic，其余 → openai。
    """

    name: str = Field(..., min_length=1, max_length=100)
    provider: str = Field(..., min_length=1, max_length=20)
    protocol: LLMProtocol | None = None
    base_url: str = Field(..., min_length=1, max_length=500)
    api_key: str = Field(..., min_length=1)
    model_name: str = Field(..., min_length=1, max_length=100)
    is_default: bool = False
    is_active: bool = True
    purpose: LLMPurpose = "chat"
    backup_config_id: int | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class LLMConfigUpdate(CamelModel):
    """更新 LLM 配置的请求 schema。

    空 ``api_key`` 表示不修改已存储的 key。
    """

    name: str | None = Field(None, min_length=1, max_length=100)
    provider: str | None = Field(None, min_length=1, max_length=20)
    protocol: LLMProtocol | None = None
    base_url: str | None = Field(None, min_length=1, max_length=500)
    api_key: str | None = Field(None, min_length=1)
    model_name: str | None = Field(None, min_length=1, max_length=100)
    is_default: bool | None = None
    is_active: bool | None = None
    purpose: LLMPurpose | None = None
    backup_config_id: int | None = None
    extra: dict[str, Any] | None = None


class LLMConfigResponse(CamelModel):
    """LLM 配置的响应 schema（API key 已脱敏）。"""

    id: int
    name: str
    provider: str
    protocol: str
    base_url: str
    model_name: str
    api_key_masked: str
    is_default: bool
    is_active: bool
    purpose: str
    backup_config_id: int | None
    degraded_until: datetime | None
    extra: dict[str, Any]
    last_tested_at: datetime | None
    last_test_status: str | None
    last_test_error: str | None
    created_at: datetime
    updated_at: datetime


class LLMConfigTestResponse(CamelModel):
    """连通性测试的响应 schema。"""

    status: str
    detail: str
    tested_at: datetime


#: AI 任务槽位键（与服务层 ``TASK_SLOTS`` 注册表同源；集合一致性由单测钉死）
TASK_KEY = Literal[
    "news_score",
    "social_sentiment",
    "news_storyline",
    "news_topic",
    "market_daily_review",
    "sector_anomaly",
    "stock_anomaly",
    "stock_daily_analysis",
    "limit_up_review",
    "chain_refresh",
]


class TaskBindingSlotResponse(CamelModel):
    """任务槽位视图：目录元信息 + 当前绑定（未绑定为 null = 跟随系统默认）。"""

    task_key: TASK_KEY
    label: str
    description: str
    config_id: int | None
    config_name: str | None
    model_name: str | None
    updated_at: datetime | None


class TaskBindingItem(CamelModel):
    """单个任务槽位的绑定项；``config_id=None`` 表示解绑（跟随系统默认）。"""

    task_key: TASK_KEY
    config_id: int | None = None


class TaskBindingReplaceRequest(CamelModel):
    """整表单保存任务绑定：非空 upsert、空删行；未携带的槽位不改动。"""

    bindings: list[TaskBindingItem]
