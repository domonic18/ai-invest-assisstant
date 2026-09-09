/** 资讯中心（/news）类型：渠道监控 + AI 分级统计，camelCase wire。 */

/** 渠道采集状态。 */
export type NewsChannelStatus = 'live' | 'ok' | 'delayed' | 'batch'

/** 渠道监控卡（后端 GET /news/channels 返回项）。 */
export interface ApiNewsChannel {
  /** 渠道标识（注册表 key，如 cls_telegraph） */
  key: string
  name: string
  status: NewsChannelStatus
  /** 状态文本（如「LIVE 采集中」「每日批次」） */
  statusText: string
  /** 轮询节奏描述（如「10s 增量轮询 · 驻留进程」） */
  pollDesc: string
  /** 今日入库条数 */
  todayCount: number
  /** 最后更新时间（ISO，渠道最新数据时间或最近任务完成时间） */
  lastUpdatedAt: string | null
  /** 数据滞后秒数（相对当前时间） */
  lagSeconds: number | null
}

/** 资讯中心全局统计条。 */
export interface ApiNewsStats {
  /** 今日资讯入库总量 */
  todayTotal: number
  /** 今日已完成 AI 分级条数 */
  scoredCount: number
  /** 今日高重要度（score ≥ 70）条数 */
  highCount: number
}

/** GET /news/channels 响应。 */
export interface ApiNewsChannelsResponse {
  channels: ApiNewsChannel[]
  stats: ApiNewsStats
}

// ============ 重点与跟踪（迭代 4） ============

/** 评分构成三维（news_ai_score.score_detail.factors，存量行无构成为 null）。 */
export interface ApiScoreFactors {
  /** 影响范围 0-100 */
  impactScope: number
  /** 确定性 0-100 */
  certainty: number
  /** 关联标的数 0-100 */
  relatedCount: number
}

/** 今日重点条目（score ≥ 70 按分排序）。 */
export interface ApiFocusItem {
  source: string
  itemId: string
  title: string | null
  content: string | null
  publishTime: string
  score: number
  factors: ApiScoreFactors | null
  reason: string | null
}

/** 故事线节点链项。 */
export interface ApiStorylineNode {
  /** ISO 时间 */
  time: string
  brief: string
}

export type ApiStorylineStatus = 'tracking' | 'near_end' | 'finished'

export type ApiStorylineOrigin = 'ai' | 'manual'

/** 故事线卡（GET /news/focus 列表项）。 */
export interface ApiStoryline {
  id: number
  title: string
  summary: string | null
  status: ApiStorylineStatus
  origin: ApiStorylineOrigin
  reportCount: number
  firstSeenAt: string
  lastSeenAt: string
  latestBrief: string | null
  nodes: ApiStorylineNode[]
  /** 当前用户跟踪操作（null=未操作，默认跟踪中） */
  userAction: 'active' | 'stopped' | null
}

/** 故事线内条目（JOIN 源表回显）。 */
export interface ApiStorylineItem {
  source: string
  itemId: string
  title: string | null
  content: string | null
  publishTime: string
  score: number | null
}

/** GET /news/focus 响应。 */
export interface ApiFocusResponse {
  highlights: ApiFocusItem[]
  storylines: ApiStoryline[]
}

/** GET /news/stories/{id} 响应。 */
export interface ApiStorylineDetail extends ApiStoryline {
  items: ApiStorylineItem[]
}

// ============ 热点主题（迭代 4，F-AI-03） ============

export type ApiTopicSentiment = '利好' | '利空' | '分歧'

/** 情绪票数分布。 */
export interface ApiTopicVotes {
  bullish: number
  bearish: number
  neutral: number
}

/** 关联板块与资金验证。 */
export interface ApiTopicSector {
  name: string
  /** 板块涨幅（%，asOfTradeDate 口径） */
  changePct: number | null
  /** 主力资金净流入（元，最近交易日口径） */
  fundFlow: number | null
}

/** 热度构成透明化：资讯量 × 板块涨幅 × 主力资金净流入。 */
export interface ApiTopicHeatFactors {
  /** 资讯量（近 24h 命中条数） */
  newsCount: number
  /** 板块涨幅口径（%）：主题关联板块的加权涨幅，无关联板块为 null */
  sectorChangePct: number | null
  /** 主力资金净流入口径（元），无数据为 null */
  fundFlowNet: number | null
  /** 板块/资金数据所属交易日（盘中跑为 T-1，前端据此标注） */
  asOfTradeDate: string | null
}

/** 传导链标的：读取时按 stock_basic + 行情快照富化，无法解析为 A 股标的时 code 为 null（不可点击）。 */
export interface ApiTopicChainStock {
  name: string
  code: string | null
  changePct: number | null
}

/** 传导链节点：事件 → 环节 → 代表标的。 */
export interface ApiTopicChainNode {
  event: string
  link: string
  stocks: ApiTopicChainStock[]
}

/** 热点主题卡。 */
export interface ApiNewsTopic {
  title: string
  sentiment: ApiTopicSentiment
  votes: ApiTopicVotes
  /** 资讯量 */
  newsCount: number
  /** 渠道分布（渠道 key → 条数） */
  channelCounts: Record<string, number>
  /** 热度 0-100（归一） */
  heat: number
  factors: ApiTopicHeatFactors
  sectors: ApiTopicSector[]
  chain: ApiTopicChainNode[]
  itemIds: string[]
}

/** 词云项。 */
export interface ApiTopicWordcloudItem {
  word: string
  count: number
}

/** GET /news/topics 响应。 */
export interface ApiTopicsResponse {
  tradeDate: string
  session: 'intraday' | 'post'
  topics: ApiNewsTopic[]
  wordcloud: ApiTopicWordcloudItem[]
  generatedAt: string | null
}

// ============ 我的订阅（迭代 4） ============

/** 订阅项（列表自带命中统计）。 */
export interface ApiSubscription {
  id: number
  keyword: string
  /** 命中渠道过滤（null=全部渠道） */
  channels: string[] | null
  pushEnabled: boolean
  enabled: boolean
  createdAt: string
  updatedAt: string
  /** 累计命中条数 */
  hitCount: number
  /** 最近命中时间（ISO，从未命中为 null） */
  lastHitAt: string | null
}
