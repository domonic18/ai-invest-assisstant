"""知识库域 Pydantic schemas（F-KB）。

两个分层：

- **LLM 输出契约**（``KbPointDraft``/``KbExtractionResult``/``EpisodeOutline``/
  ``ChapterTreeDraft``/``ImageUnderstanding``）：裸 BaseModel、全字段 required、
  禁带默认值（默认值不进 JSON Schema required，LLM 会静默省略——项目铁律；
  无数据由模型显式输出空串/空列表/null）。契约由
  ``tests/unit/services/test_structured_output_contract.py`` 钉死。
- **wire 契约**（``KbSettings*``）：CamelModel，与 ``shared/types/kb.ts``
  单一真相源对齐。
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.base import CamelModel

# ---------------------------------------------------------------------------
# LLM 输出契约（结构化抽取）
# ---------------------------------------------------------------------------

KbPointTypeLiteral = Literal["concept", "theorem", "method", "discipline", "case"]
KbConfidenceLiteral = Literal["high", "medium", "low"]


class KbPointDraft(BaseModel):
    """单条知识点草稿（抽取窗口内产出，定位/归章交给服务层校验）。"""

    title: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1)
    point_type: KbPointTypeLiteral
    confidence: KbConfidenceLiteral
    chapter_path: list[str] | None
    term_definition: str | None
    applicable_scene: str | None
    excerpt: str = Field(..., min_length=1)
    start_ms: int | None
    end_ms: int | None
    related_titles: list[str]


class KbExtractionResult(BaseModel):
    """一次抽取窗口的完整输出。"""

    points: list[KbPointDraft]


class EpisodeOutlinePoint(BaseModel):
    """单集大纲条目。"""

    title: str = Field(..., min_length=1)
    summary: str


class EpisodeOutline(BaseModel):
    """单集大纲（章节推断第一步）。"""

    episode_no: int
    points: list[EpisodeOutlinePoint]


class ChapterNodeDraft(BaseModel):
    """目录树节点草稿（节点 id 由服务层生成，保证稳定）。"""

    title: str = Field(..., min_length=1)
    children: list["ChapterNodeDraft"]


class ChapterTreeDraft(BaseModel):
    """跨集合并后的目录树草稿。"""

    nodes: list[ChapterNodeDraft]


class ImageUnderstanding(BaseModel):
    """书中图片三文本（图内文字 OCR + 图注推断 + 视觉描述）。"""

    text_in_image: str
    caption: str
    description: str


class KbTranscriptCleanItem(BaseModel):
    """清洗回填的单句（seq 与输入编号一一对应，只改文本不改时间轴）。"""

    seq: int
    text: str = Field(..., min_length=1)


class KbTranscriptCleanResult(BaseModel):
    """一次清洗批次的完整输出。"""

    items: list[KbTranscriptCleanItem]


# ---------------------------------------------------------------------------
# wire 契约（camelCase，shared/types/kb.ts 单一真相源）
# ---------------------------------------------------------------------------


class KbSettingsResponse(CamelModel):
    """知识库设置读取（含四模型角色槽位）。"""

    hotwords: list[str]
    segment_max_seconds: int
    asr_concurrency: int
    top_k: int
    auto_approve_points: bool
    unit_prices: dict[str, Any]
    embedding_config_id: int | None
    clean_model_id: int | None
    extract_model_id: int | None
    vision_model_id: int | None
    authorized_user_ids: list[int]
    updated_at: datetime | None = None


class KbSettingsUpdateRequest(CamelModel):
    """知识库设置保存（全部可选，仅提交的字段更新）。"""

    hotwords: list[str] | None = Field(None, max_length=200)
    segment_max_seconds: int | None = Field(None, ge=5, le=120)
    asr_concurrency: int | None = Field(None, ge=1, le=8)
    top_k: int | None = Field(None, ge=1, le=50)
    auto_approve_points: bool | None = None
    unit_prices: dict[str, Any] | None = None
    embedding_config_id: int | None = None
    clean_model_id: int | None = None
    extract_model_id: int | None = None
    vision_model_id: int | None = None
    authorized_user_ids: list[int] | None = Field(None, max_length=500)


class KbSourceResponse(CamelModel):
    """知识库（source）视图。"""

    id: int
    source_type: str
    name: str
    author: str | None = None
    description: str | None = None
    enabled: bool
    storage_bytes: int
    pending_cleanup_bytes: int
    deleted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class KbSourceCreateRequest(CamelModel):
    """新建知识库。"""

    source_type: Literal["course", "book"]
    name: str = Field(..., min_length=1, max_length=200)
    author: str | None = Field(None, max_length=100)
    description: str | None = Field(None, max_length=2000)
    enabled: bool = True


class KbSourceUpdateRequest(CamelModel):
    """编辑知识库（全部可选）。"""

    name: str | None = Field(None, min_length=1, max_length=200)
    author: str | None = Field(None, max_length=100)
    description: str | None = Field(None, max_length=2000)
    enabled: bool | None = None


class KbMediaResponse(CamelModel):
    """素材（media）视图。"""

    id: int
    source_id: int
    media_kind: str
    episode_no: int | None = None
    title: str | None = None
    file_name: str
    relative_path: str | None = None
    file_size: int | None = None
    file_hash: str | None = None
    duration_seconds: int | None = None
    page_count: int | None = None
    process_status: str
    process_error: str | None = None
    process_meta: dict[str, Any] = Field(default_factory=dict)
    edited_at: datetime | None = None
    deleted_at: datetime | None = None
    point_count: int = 0
    dirty_count: int = 0
    created_at: datetime
    updated_at: datetime


class KbMediaInitItem(CamelModel):
    """批量登记的单个文件（目录结构由 relativePath 保留）。"""

    file_name: str = Field(..., min_length=1, max_length=500)
    relative_path: str | None = Field(None, max_length=1000)
    size: int = Field(..., ge=1)
    hash: str = Field(..., min_length=8, max_length=64)
    media_kind: Literal["video", "audio", "book"]
    episode_no: int | None = Field(None, ge=1)
    title: str | None = Field(None, max_length=200)
    duration_seconds: int | None = Field(None, ge=0)
    page_count: int | None = Field(None, ge=0)


class KbMediaInitRequest(CamelModel):
    """上传初始化：批量建行 + 预签名 PUT。"""

    items: list[KbMediaInitItem] = Field(..., min_length=1, max_length=500)


class KbMediaInitResult(CamelModel):
    """单个文件的初始化结果（mediaId 供 uploaded 回调）。

    库内同哈希冲突的条目不抛整批 409，而是返回 conflictWith（既有素材标题），
    mediaId/cosKey/uploadUrl 为 None，由前端标记跳过。
    """

    media_id: int | None = None
    file_name: str = ""
    cos_key: str | None = None
    upload_url: str | None = None
    conflict_with: str | None = None


class KbMediaInitResponse(CamelModel):
    """批量初始化结果（与请求 items 等长同序）。"""

    items: list[KbMediaInitResult]


class KbUploadSessionRequest(CamelModel):
    """分片上传会话创建/续传请求。

    partSize/partCount 由前端按文件大小计算（S3 约束：除末片外每片 >= 5MB，
    分片数 <= 10000）；resumeUploadId 为本地续传提示，服务端以 process_meta
    内的 uploadId + list_parts 为唯一真相。
    """

    part_size: int = Field(ge=5 * 1024 * 1024)
    part_count: int = Field(ge=1, le=10000)
    resume_upload_id: str | None = None


class KbUploadSessionPart(CamelModel):
    """已完成分片（服务端 list_parts 视角）。"""

    part_number: int
    etag: str
    size: int


class KbUploadSessionPartUrl(CamelModel):
    """待上传分片的预签名 PUT URL。"""

    part_number: int
    url: str


class KbUploadSessionResponse(CamelModel):
    """分片上传会话视图：completedParts 为已传分片，partUrls 仅覆盖缺失分片。"""

    media_id: int
    upload_id: str
    part_size: int
    part_count: int
    completed_parts: list[KbUploadSessionPart]
    part_urls: list[KbUploadSessionPartUrl]


class KbMediaPatchRequest(CamelModel):
    """素材元数据修正（集号/标题/时长/页数）。"""

    episode_no: int | None = Field(None, ge=1)
    title: str | None = Field(None, max_length=200)
    duration_seconds: int | None = Field(None, ge=0)
    page_count: int | None = Field(None, ge=0)


class KbCostEstimateRequest(CamelModel):
    """费用预估请求（素材必须属于该知识库）。"""

    source_id: int
    media_ids: list[int] = Field(..., min_length=1)


class KbCostEstimateItem(CamelModel):
    """单素材费用分项（书在批次 C 接入前为 0 项）。"""

    media_id: int
    title: str
    media_kind: str
    duration_seconds: int | None = None
    asr_cost: float = 0
    clean_tokens: int = 0
    estimated_cost: float = 0


class KbCostEstimateResponse(CamelModel):
    """费用预估视图（预估即把 uploaded 素材推进到 awaiting_cost）。"""

    currency: str = "CNY"
    items: list[KbCostEstimateItem]
    total: float = 0


class KbConfirmCostRequest(CamelModel):
    """费用确认请求（awaiting_cost → queued）。"""

    media_ids: list[int] = Field(..., min_length=1)


class KbConfirmCostResponse(CamelModel):
    """费用确认结果（本次实际入队的素材）。"""

    queued_ids: list[int]


class KbTranscriptSegmentView(CamelModel):
    """文稿编辑器单行。"""

    seq_no: int
    text: str
    start_ms: int | None = None
    end_ms: int | None = None
    page_start: int | None = None
    page_end: int | None = None


class KbTranscriptResponse(CamelModel):
    """单集文稿读取。"""

    media_id: int
    edited_at: datetime | None = None
    segments: list[KbTranscriptSegmentView]


class KbTranscriptSegmentUpdate(CamelModel):
    """文稿单行修正（只改文本，时间轴只读）。"""

    seq_no: int
    text: str


class KbTranscriptUpdateRequest(CamelModel):
    """文稿批量保存（按 seqNo 覆盖文本，时间轴不变）。"""

    segments: list[KbTranscriptSegmentUpdate] = Field(..., min_length=1)


class KbTranscriptSaveResponse(CamelModel):
    """文稿保存结果（updatedCount>0 即触发脏传播）。"""

    media_id: int
    edited_at: datetime | None = None
    updated_count: int = 0


# ---------------------------------------------------------------------------
# 章节树与知识点审核（arch/12 §6，F-KB-03）
# ---------------------------------------------------------------------------


class KbChapterNode(CamelModel):
    """目录树节点（id 由服务端按位置生成，发布后被 chapter_path 引用）。"""

    id: str = Field(..., min_length=1, max_length=32)
    title: str = Field(..., min_length=1, max_length=300)
    children: list["KbChapterNode"] = []


class KbChaptersResponse(CamelModel):
    """知识源目录树（draft 供编辑发布，published 为生效版本）。"""

    draft: list[KbChapterNode] | None = None
    published: list[KbChapterNode] | None = None


class KbChaptersPublishRequest(CamelModel):
    """目录树发布（整棵提交，published 覆盖写并同步 draft）。"""

    chapters: list[KbChapterNode] = Field(..., min_length=1, max_length=200)


class KbKnowledgePointResponse(CamelModel):
    """知识点卡片视图（episodeNo/mediaTitle 为 join 冗余，供原文脚注展示）。"""

    id: int
    source_id: int
    media_id: int
    episode_no: int | None = None
    media_title: str | None = None
    point_type: str
    title: str
    body: str
    term_definition: str | None = None
    applicable_scene: str | None = None
    excerpt: str
    start_ms: int | None = None
    end_ms: int | None = None
    page_start: int | None = None
    page_end: int | None = None
    related_ids: list[int] = Field(default_factory=list)
    chapter_path: list[str] = Field(default_factory=list)
    status: str
    needs_review: bool = False
    review_note: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class KbPointCounts(CamelModel):
    """审核工作台状态计数。"""

    draft: int = 0
    published: int = 0
    rejected: int = 0
    needs_review: int = 0


class KbPointListResponse(CamelModel):
    """知识点列表（服务端分页 + 状态计数）。"""

    items: list[KbKnowledgePointResponse]
    total: int
    counts: KbPointCounts


class KbPointPatchRequest(CamelModel):
    """知识点修订（excerpt 与时间码/页码定位不可改——溯源锚点，extra 拒绝）。"""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(None, min_length=1, max_length=300)
    point_type: KbPointTypeLiteral | None = None
    body: str | None = Field(None, min_length=1)
    term_definition: str | None = Field(None, max_length=4000)
    applicable_scene: str | None = Field(None, max_length=4000)
    chapter_path: list[str] | None = Field(None, max_length=20)


class KbPointCreateRequest(CamelModel):
    """人工新增知识点（excerpt 缺省取 body 前 200 字）。"""

    media_id: int
    point_type: KbPointTypeLiteral
    title: str = Field(..., min_length=1, max_length=300)
    body: str = Field(..., min_length=1)
    term_definition: str | None = Field(None, max_length=4000)
    applicable_scene: str | None = Field(None, max_length=4000)
    excerpt: str | None = Field(None, max_length=2000)
    start_ms: int | None = Field(None, ge=0)
    end_ms: int | None = Field(None, ge=0)
    page_start: int | None = Field(None, ge=1)
    page_end: int | None = Field(None, ge=1)
    chapter_path: list[str] = Field(default_factory=list, max_length=20)


class KbPointRejectRequest(CamelModel):
    """驳回理由（写入 review_note）。"""

    reason: str | None = Field(None, max_length=1000)


class KbPointsMergeRequest(CamelModel):
    """重复草稿合并进目标卡（仅 draft 可并入，源行硬删）。"""

    target_id: int
    source_ids: list[int] = Field(..., min_length=1, max_length=50)


class KbPointsBatchApproveRequest(CamelModel):
    """批量通过草稿（单事务逐张审计；已发布/不存在幂等跳过）。"""

    ids: list[int] = Field(..., min_length=1, max_length=50)


class KbBatchApproveResult(CamelModel):
    """批量通过结果统计（skipped = 已发布或不存在的卡）。"""

    approved: int
    skipped: int


class KbImageAssetResponse(CamelModel):
    """图片资产视图（thumbUrl 为短时效签名；书嵌图/课程关键帧共用）。"""

    id: int
    source_id: int
    media_id: int
    page_no: int | None = None
    start_ms: int | None = None
    end_ms: int | None = None
    thumb_url: str | None = None
    describe_status: str
    describe_attempts: int = 0
    text_in_image: str | None = None
    caption: str | None = None
    vision_description: str | None = None
    index_excluded: bool = False
    created_at: datetime


class KbImageExcludedRequest(CamelModel):
    """图片资产索引排除开关。"""

    index_excluded: bool


class KbImageListResponse(CamelModel):
    """图片资产列表（服务端分页；检索消费留批次 E/F）。"""

    items: list[KbImageAssetResponse]
    total: int


# ---------------------------------------------------------------------------
# 混合检索（arch/12 §7.2，消费侧 /kb/search）
# ---------------------------------------------------------------------------


class KbSearchFrameHit(CamelModel):
    """案例卡片关联帧（命中时间窗内就近取帧，缩略图短时效签名）。"""

    id: int
    start_ms: int | None = None
    thumb_url: str | None = None
    caption: str | None = None


class KbSearchPointHit(CamelModel):
    """知识卡片命中（PG 水合全字段；score 为 RRF 融合分）。"""

    id: int
    source_id: int
    media_id: int
    media_kind: str
    episode_no: int | None = None
    media_title: str | None = None
    point_type: str
    title: str
    body: str
    term_definition: str | None = None
    applicable_scene: str | None = None
    excerpt: str
    chapter_path: list[str] = Field(default_factory=list)
    related_ids: list[int] = Field(default_factory=list)
    start_ms: int | None = None
    end_ms: int | None = None
    page_start: int | None = None
    page_end: int | None = None
    score: float
    frames: list[KbSearchFrameHit] = Field(default_factory=list)


class KbBrowsePointItem(CamelModel):
    """章节浏览卡片（浏览是确定性清单非相关性命中，无 score/frames）。"""

    id: int
    source_id: int
    media_id: int
    media_kind: str
    episode_no: int | None = None
    media_title: str | None = None
    point_type: str
    title: str
    body: str
    term_definition: str | None = None
    applicable_scene: str | None = None
    excerpt: str
    chapter_path: list[str] = Field(default_factory=list)
    related_ids: list[int] = Field(default_factory=list)
    start_ms: int | None = None
    end_ms: int | None = None
    page_start: int | None = None
    page_end: int | None = None


class KbChapterPointsResponse(CamelModel):
    """章节卡片清单（浏览路径：total/page/pageSize 分页）。"""

    total: int
    page: int
    page_size: int
    points: list[KbBrowsePointItem] = Field(default_factory=list)


class KbSearchSegmentHit(CamelModel):
    """原文分段命中（seekMs 为前滚后起播点 = max(0, startMs − 4s)）。"""

    id: int
    source_id: int
    media_id: int
    media_kind: str
    episode_no: int | None = None
    media_title: str | None = None
    text: str
    start_ms: int | None = None
    end_ms: int | None = None
    seek_ms: int | None = None
    score: float


class KbSearchImageHit(CamelModel):
    """图片命中（缩略图短时效签名；课程帧带时间码、书嵌图带页码）。"""

    id: int
    source_id: int
    media_id: int
    media_kind: str
    episode_no: int | None = None
    page_no: int | None = None
    start_ms: int | None = None
    text_in_image: str | None = None
    caption: str | None = None
    thumb_url: str | None = None
    score: float


class KbSearchResponse(CamelModel):
    """混合检索结果（三类命中独立列表；degraded 标记降级原因）。"""

    query: str
    degraded: str | None = None
    points: list[KbSearchPointHit] = Field(default_factory=list)
    segments: list[KbSearchSegmentHit] = Field(default_factory=list)
    images: list[KbSearchImageHit] = Field(default_factory=list)


class KbPublishedChaptersResponse(CamelModel):
    """发布态目录树（消费侧导航，不暴露 draft）。"""

    chapters: list[KbChapterNode] = Field(default_factory=list)
