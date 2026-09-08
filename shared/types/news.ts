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
