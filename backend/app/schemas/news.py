"""资讯中心 schema：AI 分级结构化输出契约与渠道监控响应。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.base import CamelModel


class NewsScoreFactors(BaseModel):
    """评分构成三维（LLM 结构化输出项，各 0-100）。"""

    impact_scope: int = Field(ge=0, le=100, description="影响范围 0-100")
    certainty: int = Field(ge=0, le=100, description="确定性 0-100")
    related_count: int = Field(ge=0, le=100, description="关联标的数 0-100")


class NewsScoreItem(BaseModel):
    """单条资讯评分（LLM 结构化输出项，source/item_id 原样回传）。"""

    source: str = Field(description="来源标识，与输入一致")
    item_id: str = Field(description="条目 ID，与输入一致")
    score: int = Field(ge=0, le=100, description="重要度 0-100")
    factors: NewsScoreFactors = Field(description="评分构成三维")
    # 必填无默认：带默认值的字段在工具 Schema 中不进 required，模型会整段省略
    reason: str = Field(description="一句话评分理由（≤40 字）")


class NewsScoreBatch(BaseModel):
    """批量评分输出契约（run_structured 的 result_type）。"""

    items: list[NewsScoreItem]


StorylineStatus = Literal["tracking", "near_end", "finished"]


class StorylineItemRef(BaseModel):
    """线内条目引用（LLM 结构化输出项，source/item_id 原样回传）。"""

    source: str = Field(description="来源标识，与输入一致")
    item_id: str = Field(description="条目 ID，与输入一致")


class StorylineDraft(BaseModel):
    """新建故事线草稿（服务层校验 ≥5 篇才落库）。"""

    title: str = Field(description="故事线标题（≤30 字）")
    summary: str = Field(description="一句话事件摘要（≤60 字）")
    status: StorylineStatus = Field(description="tracking/near_end/finished")
    latest_brief: str = Field(description="最新进展一句话（≤40 字）")
    item_refs: list[StorylineItemRef] = Field(description="聚入该线的条目引用")


class StorylineAttachment(BaseModel):
    """续接既有线：新报道挂入 + 状态与最新进展更新。"""

    storyline_id: int = Field(description="既有故事线 ID，取自输入")
    status: StorylineStatus = Field(description="tracking/near_end/finished")
    latest_brief: str = Field(description="最新进展一句话（≤40 字）")
    item_refs: list[StorylineItemRef] = Field(description="续接该线的条目引用")


class StorylineBatch(BaseModel):
    """故事线建线/续接输出契约（run_structured 的 result_type）。"""

    new_storylines: list[StorylineDraft]
    attachments: list[StorylineAttachment]


TopicSentiment = Literal["利好", "利空", "分歧"]


class TopicVotes(BaseModel):
    """主题情绪票数分布（三者和等于主题资讯数）。"""

    bullish: int = Field(ge=0, description="利好篇数")
    bearish: int = Field(ge=0, description="利空篇数")
    neutral: int = Field(ge=0, description="中性篇数")


class TopicChainStep(BaseModel):
    """传导链一步：事件 → 环节 → 代表标的。"""

    event: str = Field(description="事件/环节描述")
    link: str = Field(description="与上一步的传导关系")
    stocks: list[str] = Field(description="代表标的（代码或简称，可为空）")


class TopicDraft(BaseModel):
    """单个热点主题草稿（热度因子由服务层按库内数据拼装）。"""

    title: str = Field(description="主题名（≤12 字）")
    sentiment: TopicSentiment = Field(description="利好/利空/分歧")
    votes: TopicVotes = Field(description="情绪票数分布")
    sector_names: list[str] = Field(description="关联 A 股板块名（东财命名，≤3 个）")
    item_ids: list[str] = Field(description="主题包含的条目 ID，取自输入")
    chain: list[TopicChainStep] = Field(description="市场传导链（2-4 步）")


class TopicBatch(BaseModel):
    """热点主题聚类输出契约（run_structured 的 result_type）。"""

    topics: list[TopicDraft]


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


# ============ 重点与跟踪（迭代 4，API 响应） ============


class ScoreFactorsResponse(CamelModel):
    """评分构成三维（存量行无构成为 null）。"""

    impact_scope: int
    certainty: int
    related_count: int


class FocusItemResponse(CamelModel):
    """今日重点条目（score ≥ 70 按分排序）。"""

    source: str
    item_id: str
    title: str | None = None
    content: str | None = None
    publish_time: datetime
    score: int
    factors: ScoreFactorsResponse | None = None
    reason: str | None = None


class StorylineNodeResponse(CamelModel):
    """线内节点链项（time 为 ISO 字符串）。"""

    time: str
    brief: str


StorylineStatusValue = Literal["tracking", "near_end", "finished"]
StorylineOriginValue = Literal["ai", "manual"]
UserStorylineAction = Literal["active", "stopped"]


class StorylineResponse(CamelModel):
    """故事线卡。"""

    id: int
    title: str
    summary: str | None = None
    status: StorylineStatusValue
    origin: StorylineOriginValue
    report_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    latest_brief: str | None = None
    nodes: list[StorylineNodeResponse]
    user_action: UserStorylineAction | None = None


class FocusResponse(CamelModel):
    """GET /news/focus 响应：今日重点 + 跟踪线列表。"""

    highlights: list[FocusItemResponse]
    storylines: list[StorylineResponse]


class StorylineItemResponse(CamelModel):
    """线内条目（JOIN 源表回显）。"""

    source: str
    item_id: str
    title: str | None = None
    content: str | None = None
    publish_time: datetime | None = None
    score: int | None = None


class StorylineDetailResponse(StorylineResponse):
    """GET /news/stories/{id} 响应：线卡 + 线内条目。"""

    items: list[StorylineItemResponse]


class StorylineCreateRequest(CamelModel):
    """POST /news/stories 手动建线请求。"""

    source: str
    item_id: str


# ============ 热点主题（迭代 4，API 响应） ============


class TopicVotesResponse(CamelModel):
    """主题情绪票数分布。"""

    bullish: int
    bearish: int
    neutral: int


class TopicSectorResponse(CamelModel):
    """关联板块与资金验证。"""

    name: str
    change_pct: float | None = None
    fund_flow: float | None = None


class TopicHeatFactorsResponse(CamelModel):
    """热度构成透明化（板块/资金口径交易日供 T-1 标注）。"""

    news_count: int
    sector_change_pct: float | None = None
    fund_flow_net: float | None = None
    as_of_trade_date: str | None = None


class TopicChainStockResponse(CamelModel):
    """传导链标的（读取时按 stock_basic + 行情快照富化；无法解析的原文保留、code 为空）。"""

    name: str
    code: str | None = None
    change_pct: float | None = None


class TopicChainStepResponse(CamelModel):
    """传导链一步。"""

    event: str
    link: str
    stocks: list[TopicChainStockResponse]


class TopicResponse(CamelModel):
    """热点主题卡。"""

    title: str
    sentiment: TopicSentiment
    votes: TopicVotesResponse
    news_count: int
    channel_counts: dict[str, int]
    heat: float
    factors: TopicHeatFactorsResponse
    sectors: list[TopicSectorResponse]
    chain: list[TopicChainStepResponse]
    item_ids: list[str]


class TopicWordcloudItemResponse(CamelModel):
    """词云项。"""

    word: str
    count: int


class TopicsResponse(CamelModel):
    """GET /news/topics 响应：当日快照。"""

    trade_date: str
    session: Literal["intraday", "post"]
    topics: list[TopicResponse]
    wordcloud: list[TopicWordcloudItemResponse]
    generated_at: datetime | None = None


# ============ 我的订阅（迭代 4，API 响应） ============


class SubscriptionResponse(CamelModel):
    """订阅项（列表自带命中统计）。"""

    id: int
    keyword: str
    channels: list[str] | None = None
    push_enabled: bool
    enabled: bool
    created_at: datetime
    updated_at: datetime
    hit_count: int
    last_hit_at: datetime | None = None


class SubscriptionCreateRequest(CamelModel):
    """新增订阅请求。"""

    keyword: str
    channels: list[str] | None = None


class SubscriptionUpdateRequest(CamelModel):
    """更新订阅请求（全部可选，仅更新传入项）。"""

    channels: list[str] | None = None
    push_enabled: bool | None = None
    enabled: bool | None = None
