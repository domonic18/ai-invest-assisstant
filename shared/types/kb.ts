/**
 * 知识库域（F-KB）wire 类型：与 backend/app/schemas/kb.py CamelModel 单一真相源对齐。
 */

/** 知识库设置响应（管理后台读写共用）。 */
export interface ApiKbSettingsResponse {
  hotwords: string[]
  segmentMaxSeconds: number
  asrConcurrency: number
  topK: number
  autoApprovePoints: boolean
  unitPrices: Record<string, number>
  embeddingConfigId: number | null
  cleanModelId: number | null
  extractModelId: number | null
  visionModelId: number | null
  authorizedUserIds: number[]
  updatedAt: string | null
}

/** 知识库设置保存请求（全部可选，仅提交的字段更新）。 */
export interface ApiKbSettingsUpdateRequest {
  hotwords?: string[]
  segmentMaxSeconds?: number
  asrConcurrency?: number
  topK?: number
  autoApprovePoints?: boolean
  unitPrices?: Record<string, number>
  embeddingConfigId?: number | null
  cleanModelId?: number | null
  extractModelId?: number | null
  visionModelId?: number | null
  authorizedUserIds?: number[]
}

/** 素材类型（书的 episodeNo 恒为 null）。 */
export type ApiKbMediaKind = 'video' | 'audio' | 'book'

/** 素材处理状态机：uploaded → awaiting_cost → queued → processing → done/failed。 */
export type ApiKbProcessStatus =
  | 'uploaded'
  | 'awaiting_cost'
  | 'queued'
  | 'processing'
  | 'done'
  | 'failed'

/** 知识源视图。 */
export interface ApiKbSourceResponse {
  id: number
  sourceType: 'course' | 'book'
  name: string
  author: string | null
  description: string | null
  enabled: boolean
  storageBytes: number
  pendingCleanupBytes: number
  deletedAt: string | null
  createdAt: string
  updatedAt: string
}

/** 新建知识源请求。 */
export interface ApiKbSourceCreateRequest {
  sourceType: 'course' | 'book'
  name: string
  author?: string | null
  description?: string | null
  enabled?: boolean
}

/** 编辑知识源请求（全部可选，仅提交的字段更新）。 */
export interface ApiKbSourceUpdateRequest {
  name?: string
  author?: string | null
  description?: string | null
  enabled?: boolean
}

/** 素材视图。 */
export interface ApiKbMediaResponse {
  id: number
  sourceId: number
  mediaKind: 'video' | 'audio' | 'book'
  episodeNo: number | null
  title: string | null
  fileName: string
  relativePath: string | null
  fileSize: number | null
  fileHash: string | null
  durationSeconds: number | null
  pageCount: number | null
  processStatus: ApiKbProcessStatus
  processError: string | null
  processMeta: Record<string, unknown>
  editedAt: string | null
  deletedAt: string | null
  pointCount: number
  dirtyCount: number
  createdAt: string
  updatedAt: string
}

/** 批量登记的单个文件（目录结构由 relativePath 保留）。 */
export interface ApiKbMediaInitItem {
  fileName: string
  relativePath: string
  size: number
  hash: string
  mediaKind: 'video' | 'audio' | 'book'
  episodeNo?: number | null
  title?: string | null
  durationSeconds?: number | null
  pageCount?: number | null
}

/** 批量登记请求。 */
export interface ApiKbMediaInitRequest {
  items: ApiKbMediaInitItem[]
}

/** 批量登记结果（每文件一行，与请求 items 等长同序；conflictWith 非空表示该文件与库内已有素材重复、被跳过）。 */
export interface ApiKbMediaInitResult {
  mediaId: number | null
  fileName: string
  cosKey: string | null
  uploadUrl: string | null
  conflictWith: string | null
}

export interface ApiKbMediaInitResponse {
  items: ApiKbMediaInitResult[]
}

/** 分片上传会话创建/续传请求（partSize/partCount 由前端按文件大小计算）。 */
export interface ApiKbUploadSessionRequest {
  partSize: number
  partCount: number
  resumeUploadId?: string | null
}

/** 已完成分片（服务端 list_parts 真相）。 */
export interface ApiKbUploadSessionPart {
  partNumber: number
  etag: string
  size: number
}

/** 待上传分片的预签名 PUT URL。 */
export interface ApiKbUploadSessionPartUrl {
  partNumber: number
  url: string
}

/** 分片上传会话视图：completedParts 已传分片，partUrls 仅覆盖缺失分片。 */
export interface ApiKbUploadSessionResponse {
  mediaId: number
  uploadId: string
  partSize: number
  partCount: number
  completedParts: ApiKbUploadSessionPart[]
  partUrls: ApiKbUploadSessionPartUrl[]
}

/** 素材信息修正请求（全部可选）。 */
export interface ApiKbMediaPatchRequest {
  episodeNo?: number | null
  title?: string
  durationSeconds?: number | null
  pageCount?: number | null
}

/** 费用预估请求（素材必须属于该知识库）。 */
export interface ApiKbCostEstimateRequest {
  sourceId: number
  mediaIds: number[]
}

/** 单素材费用分项（书在批次 C 接入前为 0 项）。 */
export interface ApiKbCostEstimateItem {
  mediaId: number
  title: string
  mediaKind: string
  durationSeconds: number | null
  asrCost: number
  cleanTokens: number
  estimatedCost: number
}

/** 费用预估视图（预估即把 uploaded 素材推进到 awaiting_cost）。 */
export interface ApiKbCostEstimateResponse {
  currency: string
  items: ApiKbCostEstimateItem[]
  total: number
}

/** 费用确认请求（awaiting_cost → queued）。 */
export interface ApiKbConfirmCostRequest {
  mediaIds: number[]
}

/** 费用确认结果（本次实际入队的素材）。 */
export interface ApiKbConfirmCostResponse {
  queuedIds: number[]
}

/** 文稿分段视图（时间轴只读，编辑只覆盖 text）。 */
export interface ApiKbTranscriptSegmentView {
  seqNo: number
  text: string
  startMs: number | null
  endMs: number | null
  pageStart: number | null
  pageEnd: number | null
}

/** 单集文稿读取。 */
export interface ApiKbTranscriptResponse {
  mediaId: number
  editedAt: string | null
  segments: ApiKbTranscriptSegmentView[]
}

/** 文稿批量保存请求（按 seqNo 覆盖文本）。 */
export interface ApiKbTranscriptUpdateRequest {
  segments: { seqNo: number; text: string }[]
}

/** 文稿保存结果（updatedCount>0 即触发脏传播）。 */
export interface ApiKbTranscriptSaveResponse {
  mediaId: number
  editedAt: string | null
  updatedCount: number
}

// ---------------------------------------------------------------------------
// 知识审核（F-KB-03）
// ---------------------------------------------------------------------------

/** 知识点类型。 */
export type ApiKbPointType = 'concept' | 'theorem' | 'method' | 'discipline' | 'case'

/** 审核状态（仅 published 参与检索）。 */
export type ApiKbPointStatus = 'draft' | 'published' | 'rejected'

/** 章节树节点（id 服务端按位置生成："1"/"1.2"）。 */
export interface ApiKbChapterNode {
  id: string
  title: string
  children: ApiKbChapterNode[]
}

/** 目录树读取（draft 供编辑，published 为生效版本）。 */
export interface ApiKbChaptersResponse {
  draft: ApiKbChapterNode[] | null
  published: ApiKbChapterNode[] | null
}

/** 目录树整棵发布请求。 */
export interface ApiKbChaptersPublishRequest {
  chapters: ApiKbChapterNode[]
}

/** 知识点卡片视图（episodeNo/mediaTitle 为 join 冗余，供原文脚注展示）。 */
export interface ApiKbKnowledgePoint {
  id: number
  sourceId: number
  mediaId: number
  episodeNo: number | null
  mediaTitle: string | null
  pointType: ApiKbPointType
  title: string
  body: string
  termDefinition: string | null
  applicableScene: string | null
  excerpt: string
  startMs: number | null
  endMs: number | null
  pageStart: number | null
  pageEnd: number | null
  relatedIds: number[]
  chapterPath: string[]
  status: ApiKbPointStatus
  needsReview: boolean
  reviewNote: string | null
  reviewedAt: string | null
  createdAt: string
  updatedAt: string
}

/** 审核工作台状态计数。 */
export interface ApiKbPointCounts {
  draft: number
  published: number
  rejected: number
  needsReview: number
}

/** 知识点分页列表。 */
export interface ApiKbPointListResponse {
  items: ApiKbKnowledgePoint[]
  total: number
  counts: ApiKbPointCounts
}

/** 白名单修订请求（excerpt/时间码定位字段服务端拒绝为 422）。 */
export interface ApiKbPointPatchRequest {
  title?: string
  pointType?: ApiKbPointType
  body?: string
  termDefinition?: string | null
  applicableScene?: string | null
  chapterPath?: string[]
}

/** 图片视觉描述状态。 */
export type ApiKbDescribeStatus = 'pending' | 'processing' | 'done' | 'failed'

/** 图片资产视图（书嵌图 + 课程关键帧；thumbUrl 为短时效签名）。 */
export interface ApiKbImageAsset {
  id: number
  sourceId: number
  mediaId: number
  pageNo: number | null
  startMs: number | null
  endMs: number | null
  thumbUrl: string | null
  describeStatus: ApiKbDescribeStatus
  describeAttempts: number
  textInImage: string | null
  caption: string | null
  visionDescription: string | null
  indexExcluded: boolean
  createdAt: string
}

/** 图片资产索引排除开关。 */
export interface ApiKbImageExcludedRequest {
  indexExcluded: boolean
}

/** 图片资产分页列表。 */
export interface ApiKbImageListResponse {
  items: ApiKbImageAsset[]
  total: number
}

/** 人工新增请求（status=draft 走同一审核流）。 */
export interface ApiKbPointCreateRequest {
  mediaId: number
  pointType: ApiKbPointType
  title: string
  body: string
  termDefinition?: string
  applicableScene?: string
  excerpt?: string
  startMs?: number
  endMs?: number
  pageStart?: number
  pageEnd?: number
  chapterPath?: string[]
}

/** 驳回请求（理由入 review_note）。 */
export interface ApiKbPointRejectRequest {
  reason?: string | null
}

/** 重复草稿合并请求（source 行硬删，related 并集进目标）。 */
export interface ApiKbPointsMergeRequest {
  targetId: number
  sourceIds: number[]
}

/** 批量通过请求（已发布/不存在幂等跳过）。 */
export interface ApiKbPointsBatchApproveRequest {
  ids: number[]
}

/** 批量通过结果统计（skipped = 已发布或不存在的卡）。 */
export interface ApiKbBatchApproveResult {
  approved: number
  skipped: number
}

// ---------------------------------------------------------------------------
// 混合检索（消费侧 /kb/search）
// ---------------------------------------------------------------------------

/** 案例卡片关联帧（命中时间窗内就近取帧，thumbUrl 短时效签名）。 */
export interface ApiKbSearchFrameHit {
  id: number
  startMs: number | null
  thumbUrl: string | null
  caption: string | null
}

/** 知识卡片命中（PG 水合全字段；score 为 RRF 融合分）。 */
export interface ApiKbSearchPointHit {
  id: number
  sourceId: number
  mediaId: number
  mediaKind: ApiKbMediaKind
  episodeNo: number | null
  mediaTitle: string | null
  pointType: ApiKbPointType
  title: string
  body: string
  termDefinition: string | null
  applicableScene: string | null
  excerpt: string
  chapterPath: string[]
  relatedIds: number[]
  startMs: number | null
  endMs: number | null
  pageStart: number | null
  pageEnd: number | null
  score: number
  frames: ApiKbSearchFrameHit[]
}

/** 原文分段命中（seekMs = max(0, startMs − 4s) 前滚起播点）。 */
export interface ApiKbSearchSegmentHit {
  id: number
  sourceId: number
  mediaId: number
  mediaKind: ApiKbMediaKind
  episodeNo: number | null
  mediaTitle: string | null
  text: string
  startMs: number | null
  endMs: number | null
  seekMs: number | null
  score: number
}

/** 图片命中（课程帧带时间码、书嵌图带页码）。 */
export interface ApiKbSearchImageHit {
  id: number
  sourceId: number
  mediaId: number
  mediaKind: ApiKbMediaKind
  episodeNo: number | null
  pageNo: number | null
  startMs: number | null
  textInImage: string | null
  caption: string | null
  thumbUrl: string | null
  score: number
}

/** 混合检索结果（三类命中独立列表；degraded 标记降级原因）。 */
export interface ApiKbSearchResponse {
  query: string
  degraded: string | null
  points: ApiKbSearchPointHit[]
  segments: ApiKbSearchSegmentHit[]
  images: ApiKbSearchImageHit[]
}

/** 发布态章节树（消费侧导航，不含 draft）。 */
export interface ApiKbPublishedChaptersResponse {
  chapters: ApiKbChapterNode[]
}

/** 章节浏览卡片（确定性清单非相关性命中，无 score/frames）。 */
export interface ApiKbBrowsePointItem {
  id: number
  sourceId: number
  mediaId: number
  mediaKind: ApiKbMediaKind
  episodeNo: number | null
  mediaTitle: string | null
  pointType: ApiKbPointType
  title: string
  body: string
  termDefinition: string | null
  applicableScene: string | null
  excerpt: string
  chapterPath: string[]
  relatedIds: number[]
  startMs: number | null
  endMs: number | null
  pageStart: number | null
  pageEnd: number | null
}

/** 章节卡片清单（浏览路径：PG 真相源 + episode/startMs 确定性排序分页）。 */
export interface ApiKbChapterPointsResponse {
  total: number
  page: number
  pageSize: number
  points: ApiKbBrowsePointItem[]
}

/** 播放凭证（prev/nextMediaId 供播放器切集；书素材携带 pageCount）。 */
export interface ApiKbPlaybackToken {
  token: string
  expiresIn: number
  mediaId: number
  /** 同时效预签名 GET 直链（video/audio）；book 为 None（书页走 token 代理渲染水印）。 */
  streamUrl: string | null
  prevMediaId: number | null
  nextMediaId: number | null
  pageCount: number | null
}

/** 消费侧知识库条目（启用中库的最小投影）。 */
export interface ApiKbConsumerSource {
  id: number
  name: string
  sourceType: 'course' | 'book'
}

/** 图片原图短时效预签名 URL（≤15min，点击原图时签发）。 */
export interface ApiKbImageUrl {
  url: string
  expiresIn: number
}

/** 用量聚合：kb_* token 分项（feature ∈ kb_clean/kb_extract/kb_vision/kb_embed）。 */
export interface ApiKbUsageTokenItem {
  feature: string
  modelName: string | null
  calls: number
  promptTokens: number
  completionTokens: number
  totalTokens: number
  /** 仅视觉分项按 vlmPerImage × 调用次数估算 */
  estimatedCost: number | null
}

/** 用量聚合：ASR 时长与费用（按时长计费，不走 token 台账）。 */
export interface ApiKbUsageAsr {
  mediaCount: number
  audioSeconds: number
  /** duration 登记口径合计（预估对照） */
  estimatedSeconds: number
  costPerHour: number | null
  cost: number | null
}

/** 建库用量聚合响应（token 分项 + ASR + 预估对照，CNY）。 */
export interface ApiKbUsageResponse {
  sourceId: number | null
  dateFrom: string | null
  dateTo: string | null
  currency: string
  tokenItems: ApiKbUsageTokenItem[]
  asr: ApiKbUsageAsr
  cleanTokensPredicted: number
  cleanTokensActual: number
  totalCost: number
}
