"""资讯中心 schema：AI 分级结构化输出契约与渠道监控响应。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.base import CamelModel


class NewsScoreItem(BaseModel):
    """单条资讯评分（LLM 结构化输出项，source/item_id 原样回传）。"""

    source: str = Field(description="来源标识，与输入一致")
    item_id: str = Field(description="条目 ID，与输入一致")
    score: int = Field(ge=0, le=100, description="重要度 0-100")
    # 必填无默认：带默认值的字段在工具 Schema 中不进 required，模型会整段省略
    reason: str = Field(description="一句话评分理由（≤40 字）")


class NewsScoreBatch(BaseModel):
    """批量评分输出契约（run_structured 的 result_type）。"""

    items: list[NewsScoreItem]


NewsChannelStatus = Literal["live", "ok", "delayed", "batch"]


class NewsChannelResponse(CamelModel):
    """渠道监控卡（GET /news/channels 返回项）。"""

    key: str
    name: str
    status: NewsChannelStatus
    status_text: str
    poll_desc: str
    today_count: int
    last_updated_at: datetime | None = None
    lag_seconds: int | None = None


class NewsStatsResponse(CamelModel):
    """资讯中心全局统计条。"""

    today_total: int
    scored_count: int
    high_count: int


class NewsChannelsResponse(CamelModel):
    """GET /news/channels 响应：渠道卡 + 今日统计。"""

    channels: list[NewsChannelResponse]
    stats: NewsStatsResponse
