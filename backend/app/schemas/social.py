"""社媒大 V 情绪 schema：LLM 判断契约（全 required 无默认）与 API 响应模型。

合规边界：任何响应模型不得包含 transcript_text（临时文稿判后即清）。
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.base import CamelModel

# ============ LLM 判断契约（run_structured 的 result_type，铁律：全 required 禁默认值） ============

SocialStanceValue = Literal["bullish", "bearish", "neutral"]


class SocialTarget(BaseModel):
    """影响标的（LLM 结构化输出项）。"""

    target_type: Literal["index", "sector", "stock", "commodity"] = Field(
        description="标的市场对象类型：大盘指数/行业板块/个股/大宗商品"
    )
    name: str = Field(description="标的名称，与博主原话一致")
    # 必填无默认：带默认值的字段在工具 Schema 中不进 required，模型会整段省略
    code: str | None = Field(description="个股/指数代码，非代码型标的为 null")


class SocialJudgmentResult(BaseModel):
    """单条内容多空判断输出契约（与 social_sentiment 落库字段一一对应）。"""

    relevance: bool = Field(description="是否与市场相关（生活/广告内容为 false）")
    stance: SocialStanceValue = Field(description="多空立场：bullish/bearish/neutral")
    confidence: float = Field(ge=0, le=1, description="判断置信度 0-1")
    core_arguments: list[str] = Field(description="核心论点列表，每条一句话")
    targets: list[SocialTarget] = Field(description="影响标的列表，无则空数组")
    summary: str = Field(description="一句话摘要（≤60 字）")


class SocialJudgmentBatchItem(SocialJudgmentResult):
    """批量判断的单条输出（post_id 由输入原样带回，服务层按其回填）。"""

    post_id: int = Field(description="待判条目的 post_id，原样返回")


class SocialJudgmentBatch(BaseModel):
    """批量判断输出契约：与输入条目一一对应，禁止编造输入之外的条目。"""

    items: list[SocialJudgmentBatchItem] = Field(description="判断结果列表")


# ============ 用户侧响应（GET /social/*） ============

StanceCount = Literal["bullish", "bearish", "neutral"]


class SocialTargetResponse(CamelModel):
    """影响标的（wire 视图；与 LLM 契约 SocialTarget 字段一致，camelCase 输出）。"""

    target_type: Literal["index", "sector", "stock", "commodity"]
    name: str
    code: str | None = None


class SocialFeedItemResponse(CamelModel):
    """情绪流卡片（post + account + sentiment 联查派生）。"""

    post_id: int
    video_id: str
    platform: str
    account_id: int
    account_alias: str
    category: str
    title: str | None = None
    caption: str | None = None
    topic_tags: list[str]
    cover_url: str | None = None
    duration_seconds: int | None = None
    published_at: datetime
    digg_count: int | None = None
    comment_count: int | None = None
    share_count: int | None = None
    transcript_missing: bool
    is_relevant: bool
    stance: StanceCount
    confidence: float
    core_arguments: list[str]
    targets: list[SocialTargetResponse]
    summary: str


class SocialFeedResponse(CamelModel):
    """GET /social/sentiment-feed 响应：分页情绪流。"""

    items: list[SocialFeedItemResponse]
    total: int
    page: int
    page_size: int


class SocialDailyStanceResponse(CamelModel):
    """账号卡按日多空分布行（发布时间转北京时间按日聚合）。"""

    date: date
    bullish: int = 0
    bearish: int = 0
    neutral: int = 0


class SocialAccountCardResponse(CamelModel):
    """账号维度卡（统计窗口内多空分布与按日时序由服务层聚合）。"""

    id: int
    alias: str
    category: str
    last_post_at: datetime | None = None
    latest_stance: StanceCount | None = None
    latest_confidence: float | None = None
    latest_summary: str | None = None
    latest_cover_url: str | None = None
    bullish_count: int = 0
    bearish_count: int = 0
    neutral_count: int = 0
    daily: list[SocialDailyStanceResponse] = []


class SocialAccountsResponse(CamelModel):
    """GET /social/accounts 响应。"""

    accounts: list[SocialAccountCardResponse]


class SocialTimelineItemResponse(CamelModel):
    """单账号已判内容时间线项（立场轨迹由前端按序派生）。"""

    post_id: int
    video_id: str
    title: str | None = None
    published_at: datetime
    stance: StanceCount
    confidence: float
    summary: str
    transcript_missing: bool


class SocialTimelineResponse(CamelModel):
    """GET /social/accounts/{id}/timeline 响应。"""

    items: list[SocialTimelineItemResponse]
    total: int
    page: int
    page_size: int


# ============ 管理侧（GET/POST/PATCH/DELETE /admin/social/*） ============


class SocialAccountCreateRequest(CamelModel):
    """登记追踪账号（sec_uid 支持直接 ID / 标准主页链接 / 分享短链）。"""

    platform: str = "douyin"
    sec_uid_or_url: str = Field(min_length=1, description="sec_uid 或主页分享链接")
    alias: str = Field(min_length=1, max_length=64)
    category: str = "finance_kol"
    poll_interval_minutes: int | None = None
    remark: str | None = None


class SocialAccountUpdateRequest(CamelModel):
    """更新追踪账号（全部可选，仅更新传入项）。"""

    alias: str | None = None
    category: str | None = None
    poll_interval_minutes: int | None = None
    is_active: bool | None = None
    remark: str | None = None


class SocialAccountAdminResponse(CamelModel):
    """管理端账号行（含诊断列）。"""

    id: int
    platform: str
    sec_uid: str
    alias: str
    category: str
    poll_interval_minutes: int
    is_active: bool
    remark: str | None = None
    last_collected_at: datetime | None = None
    last_post_at: datetime | None = None
    last_error: str | None = None
    last_error_at: datetime | None = None
    created_at: datetime


class SocialBackfillResponse(CamelModel):
    """POST /admin/social/accounts/{id}/backfill 响应：派发日志定位。"""

    log_id: int
    celery_task_id: str | None = None


class SocialPostDebugResponse(CamelModel):
    """GET /admin/social/accounts/{id}/posts 行：作品级排查（转写/判级状态）。"""

    video_id: str
    title: str | None = None
    cover_url: str | None = None
    published_at: datetime
    transcript_status: str
    transcript_reason: str | None = None
    judged_at: datetime | None = None
    is_relevant: bool | None = None
    stance: str | None = None
    confidence: float | None = None


class SocialPostsDebugResponse(CamelModel):
    """GET /admin/social/accounts/{id}/posts 响应：最近作品排查清单。"""

    items: list[SocialPostDebugResponse]


class SocialAccountsAdminResponse(CamelModel):
    """GET /admin/social/accounts 响应：分页清单。"""

    items: list[SocialAccountAdminResponse]
    total: int
    page: int
    page_size: int


class DouyinStatusResponse(CamelModel):
    """抖音适配层健康（Cookie 池 + 今日采集量）。"""

    cookie_configured: bool
    cookie_jars_available: int
    last_bootstrap_at: datetime | None = None
    signature_warning: bool
    today_collected: int
    today_failed: int


class AsrStatusResponse(CamelModel):
    """ASR 转写服务状态。"""

    enabled: bool
    configured: bool
    today_transcribed: int
    today_degraded: int
    today_pending: int = 0


class SignerStatusResponse(CamelModel):
    """抖音签名 sidecar 状态（未配置 URL 时 enabled=False）。"""

    enabled: bool
    reachable: bool
    warm_slots: int | None = None
    detail: str | None = None


class SocialStatusResponse(CamelModel):
    """GET /admin/social/status 响应：只读聚合。"""

    douyin: DouyinStatusResponse
    asr: AsrStatusResponse
    signer: SignerStatusResponse


class CookieImportRequest(CamelModel):
    """POST /admin/social/cookies 请求：粘贴整串 Cookie（ttwid 必需）。"""

    cookie: str = Field(min_length=1, description="浏览器复制的完整 Cookie 串")


class CookieImportResponse(CamelModel):
    """POST /admin/social/cookies 响应：导入后的 jar 池可用数。"""

    cookie_jars_available: int
