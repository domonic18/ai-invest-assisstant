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
