/** Agent 执行会话管理（D35）：自动化任务执行轨迹观测的 wire 类型。 */

import type { ApiPaginatedResponse } from './api'

/** 会话状态：running 执行中 / success 成功 / failed 失败 / skipped 缓存命中等未执行。 */
export type AgentRunStatus = 'running' | 'success' | 'failed' | 'skipped'

/** 会话类型：plan 每日选股计划 / review 分层复盘。 */
export type AgentRunKind = 'plan' | 'review'

/** 触发方式：scheduled 定时 / manual 手动。 */
export type AgentRunTriggerType = 'scheduled' | 'manual'

/** 会话头：一次生成（plan/review 各一次一条）的触发方式、状态与结果摘要。 */
export interface ApiAgentRun {
  id: number
  agentKey: string
  kind: AgentRunKind
  period: string | null
  triggerType: AgentRunTriggerType
  tradeDate: string | null
  status: AgentRunStatus
  startedAt: string
  finishedAt: string | null
  durationMs: number | null
  errorMsg: string | null
  /** 结果摘要：cacheHit / kbUsed / selections / plans / droppedCodes 等，结构随 kind。 */
  summary: Record<string, unknown> | null
  /** 关联 collector_log.id（定时链路溯源，手动触发为空）。 */
  collectorLogId: number | null
}

/** 执行步骤明细（聊天式时间线节点）。payload 结构由 stepKey 决定。 */
export interface ApiAgentRunStep {
  seq: number
  stepKey: string
  title: string | null
  status: 'success' | 'failed'
  startedAt: string | null
  durationMs: number | null
  /** 步骤完整输入输出（代码层 8KB/段截断；prompt/结构化输出 64KB）。 */
  payload: Record<string, unknown> | null
}

/** 会话详情：头部 + 按 seq 升序的步骤时间线。 */
export interface ApiAgentRunDetail extends ApiAgentRun {
  steps: ApiAgentRunStep[]
}

/** 会话列表分页响应。 */
export interface ApiAgentRunListResponse extends ApiPaginatedResponse<ApiAgentRun> {}
