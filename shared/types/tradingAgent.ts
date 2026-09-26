/**
 * 交易 Agent wire 类型（与 backend/app/schemas/paper_trade.py 的
 * TradingAgentConfig* camelCase 对齐；docs/plan/paper-trading-plan.md §8）。
 */

/** 交易 Agent 全局配置（单例）。 */
export interface ApiTradingAgentConfig {
  /** 绑定的 llm_config 条目 id；null = 平台默认 chat 模型。 */
  llmConfigId?: number | null
  /** 单票市值 ≤ 总资产 %。 */
  riskMaxPositionPct: number
  /** 总持仓市值 ≤ 总资产 %。 */
  riskMaxTotalPct: number
  /** 单日委托笔数上限。 */
  riskMaxDailyOrders: number
  /** 盘中自主执行总闸（批次 8 消费）。 */
  autoExecEnabled: boolean
  updatedAt?: string | null
}

/** 交易 Agent 配置保存请求（未提供字段不变）。 */
export interface ApiTradingAgentConfigUpdateRequest {
  llmConfigId?: number | null
  riskMaxPositionPct?: number
  riskMaxTotalPct?: number
  riskMaxDailyOrders?: number
  autoExecEnabled?: boolean
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
