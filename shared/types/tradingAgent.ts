/**
 * 交易 Agent wire 类型（与 backend/app/schemas/paper_trade.py 的
 * TradingAgentProfile / AgentOverview 系列 camelCase 对齐；docs/plan/agent-hub-plan.md）。
 */

/** 交易 Agent 注册行视图（身份/介绍/模型绑定/风控/总闸）。 */
export interface TradingAgentProfile {
  agentKey: string
  name: string
  tagline: string
  strategyDesc: string
  styleDesc: string
  /** 绑定的 llm_config 条目 id；null = 平台默认 chat 模型。 */
  llmConfigId: number | null
  /** 方法论知识源（kb_source.id）；null = 未启用方法论基座注入。 */
  methodologySourceId: number | null
  /** 单票市值 ≤ 总资产 %。 */
  riskMaxPositionPct: number
  /** 总持仓市值 ≤ 总资产 %。 */
  riskMaxTotalPct: number
  /** 单日委托笔数上限。 */
  riskMaxDailyOrders: number
  /** 盘中自主执行总闸（盘中执行批次消费）。 */
  autoExecEnabled: boolean
  status: 'active' | 'planned' | 'disabled'
  /** 计划生成频率（daily 每交易日 / weekly 周期末 / monthly 月末，D28）。 */
  planCadence: 'daily' | 'weekly' | 'monthly'
  /** 复盘生成频率（同上）。 */
  reviewCadence: 'daily' | 'weekly' | 'monthly'
  sortOrder: number
  promptId: string
  accentColor: string
  updatedAt?: string | null
}

/** Agent 计划/复盘生成频率（D28：daily 每交易日 / weekly 周期末 / monthly 月末）。 */
export type AgentCadence = 'daily' | 'weekly' | 'monthly'

/** 交易 Agent 配置保存请求（未提供字段不变；任意状态可写，D28）。
 * status 仅接受 active/disabled——'planned' 为种子初始态，启用即置 active。 */
export interface TradingAgentProfileUpdateRequest {
  name?: string
  tagline?: string
  strategyDesc?: string
  styleDesc?: string
  llmConfigId?: number | null
  methodologySourceId?: number | null
  riskMaxPositionPct?: number
  riskMaxTotalPct?: number
  riskMaxDailyOrders?: number
  autoExecEnabled?: boolean
  status?: 'active' | 'disabled'
  planCadence?: AgentCadence
  reviewCadence?: AgentCadence
}

/** 总览近期活动条目（计划生成/触发、复盘生成）。 */
export interface AgentActivityItem {
  kind: 'plan' | 'review'
  title: string
  detail?: string | null
  occurredAt?: string | null
}

/** 总览「接下来」条目：后端按 cron + 交易日历算好的下次触发时刻（UTC）。 */
export interface AgentNextTask {
  task: string
  scheduledAt: string
}

/** 总览页单 Agent 聚合：介绍卡 + 模型 + 当日计数 + 近期活动 + 下次任务。 */
export interface AgentOverviewItem {
  profile: TradingAgentProfile
  llmName: string | null
  planCount: number
  selectionCount: number
  orderCount: number
  recentActivity: AgentActivityItem[]
  nextTasks: AgentNextTask[]
}

/** 总览页聚合载荷（GET /admin/trading-agent/agents）。 */
export interface AgentOverviewResponse {
  items: AgentOverviewItem[]
  generatedAt: string
}

/** 复盘周期。 */
export type TradingReviewPeriod = 'day' | 'week' | 'month'

/** 单笔委托三层判定（selection=该不该做 / plan=计划 / execution=执行）。 */
export interface ApiTradingAgentTradeVerdict {
  clOrdId: string
  stockCode: string
  selectionVerdict: 'correct' | 'wrong' | 'neutral'
  planVerdict: 'correct' | 'wrong' | 'neutral'
  executionVerdict: 'correct' | 'wrong' | 'neutral'
  reason: string
}

/** 复盘提取的经验条目（批次 9 沉淀为 agent_memory 的直接来源）。 */
export interface ApiTradingAgentReviewExperience {
  title: string
  body: string
  memType: 'discipline' | 'method' | 'lesson'
}

/** 模拟盘分层复盘（admin GET /trading-agent/review，只读缓存）。 */
export interface ApiTradingAgentReview {
  period: TradingReviewPeriod
  tradeDate: string
  overall: string
  trades: ApiTradingAgentTradeVerdict[]
  bias: string
  suggestion: string
  experiences: ApiTradingAgentReviewExperience[]
}

/** 有记录日期清单（日历打点：计划日 + 各周期复盘基准日）。 */
export interface ApiTradingAgentDates {
  planDates: string[]
  reviewDates: Partial<Record<TradingReviewPeriod, string[]>>
}

/** 计划状态机（active → triggered → executed / expired / cancelled）。 */
export type TradingAgentPlanStatus = 'active' | 'triggered' | 'executed' | 'expired' | 'cancelled'

/** 交易计划条目（admin GET /trading-agent/plans 与「今日交易计划」区块）。 */
export interface ApiTradingAgentPlan {
  id: number
  planDate: string
  stockCode: string
  planType: 'buy' | 'sell'
  strategy: string
  buyZoneLow: number | null
  buyZoneHigh: number | null
  targetPrice: number | null
  stopLoss: number
  positionPct: number
  status: TradingAgentPlanStatus
  selectionId: number | null
  basis: string
  triggeredClOrdId: string | null
}

/** agent 选股条目（模拟管理「Agent 自选」：AI 依据 + 置信度）。 */
export interface ApiAgentWatchlistSelectionItem {
  id: number
  stockCode: string
  reason: string
  confidence: number | null
  tradeDate: string
}

/** agent 自选分组（admin GET /trading-agent/selections；null = 尚未生成选股）。 */
export interface ApiAgentWatchlistGroupResponse {
  id: number
  name: string
  items: ApiAgentWatchlistSelectionItem[]
}

/** agent 记忆类型（discipline 纪律 / method 方法 / lesson 教训）。 */
export type AgentMemoryType = 'discipline' | 'method' | 'lesson'

/** agent 记忆条目（admin GET /trading-agent/memories；active 条目注入每日计划 prompt）。 */
export interface ApiAgentMemory {
  id: number
  memType: AgentMemoryType
  title: string
  body: string
  source: 'auto' | 'manual'
  status: 'active' | 'archived'
  sourceResultId: number | null
  createdAt: string
  updatedAt: string
}

/** agent 记忆编辑请求（未提供字段不变）。 */
export interface ApiAgentMemoryUpdateRequest {
  title?: string
  body?: string
  memType?: AgentMemoryType
}
