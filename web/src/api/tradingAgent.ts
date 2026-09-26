/** 交易 Agent API（admin /admin/trading-agent/{agentKey}/*，多 Agent 路径参数）。 */

import { ENDPOINTS } from '@ai-invest/shared'
import type {
  AgentMemoryType,
  AgentOverviewResponse,
  ApiAgentCapabilityResponse,
  ApiAgentMemory,
  ApiAgentMemoryUpdateRequest,
  ApiAgentWatchlistGroupResponse,
  ApiTradingAgentDates,
  ApiTradingAgentPlan,
  ApiTradingAgentPlansResponse,
  ApiTradingAgentPromptTemplate,
  ApiTradingAgentReview,
  TradingAgentCreateRequest,
  TradingAgentProfile,
  TradingAgentProfileUpdateRequest,
  TradingReviewPeriod,
} from '@ai-invest/shared'

import { apiClient } from './client'

/** 全部注册 Agent 总览聚合（介绍卡 + 计数 + 近期活动 + 下次任务）。 */
export async function fetchAgentOverview(): Promise<AgentOverviewResponse> {
  const response = await apiClient.get<AgentOverviewResponse>(
    ENDPOINTS.admin.tradingAgentAgents,
  )
  return response.data
}

/** Agent 能力/状态视图（人设/方法论/作业技能/模型/记忆/自动化任务/近期活动）。 */
export async function fetchTradingAgentStatus(
  agentKey: string,
): Promise<ApiAgentCapabilityResponse> {
  const response = await apiClient.get<ApiAgentCapabilityResponse>(
    ENDPOINTS.admin.tradingAgentStatus(agentKey),
  )
  return response.data
}

/** 可用会话人设模板清单（新建 Agent 下拉）。 */
export async function fetchTradingAgentPromptTemplates(): Promise<
  ApiTradingAgentPromptTemplate[]
> {
  const response = await apiClient.get<ApiTradingAgentPromptTemplate[]>(
    ENDPOINTS.admin.tradingAgentPromptTemplates,
  )
  return response.data
}

/** 新建 Agent（创建即 active 参与调度；绑定账户后才实际下单）。 */
export async function createTradingAgent(
  data: TradingAgentCreateRequest,
): Promise<TradingAgentProfile> {
  const response = await apiClient.post<TradingAgentProfile>(
    ENDPOINTS.admin.tradingAgentAgents,
    data,
  )
  return response.data
}

/** 删除 Agent 并级联清理（解绑模拟盘账户、删计划/选股/记忆/会话）。 */
export async function deleteTradingAgent(agentKey: string): Promise<void> {
  await apiClient.delete(ENDPOINTS.admin.tradingAgentAgent(agentKey))
}

export async function fetchTradingAgentConfig(agentKey: string): Promise<TradingAgentProfile> {
  const response = await apiClient.get<TradingAgentProfile>(
    ENDPOINTS.admin.tradingAgentConfig(agentKey),
  )
  return response.data
}

export async function updateTradingAgentConfig(
  agentKey: string,
  data: TradingAgentProfileUpdateRequest,
): Promise<TradingAgentProfile> {
  const response = await apiClient.put<TradingAgentProfile>(
    ENDPOINTS.admin.tradingAgentConfig(agentKey),
    data,
  )
  return response.data
}

export async function fetchTradingAgentReview(
  agentKey: string,
  period: TradingReviewPeriod,
  tradeDate?: string,
): Promise<ApiTradingAgentReview> {
  const response = await apiClient.get<ApiTradingAgentReview>(
    ENDPOINTS.admin.tradingAgentReview(agentKey),
    { params: tradeDate ? { period, trade_date: tradeDate } : { period } },
  )
  return response.data
}

/** 有记录日期清单（日历打点：计划日 + 各周期已生成复盘的基准日）。 */
export async function fetchTradingAgentDates(agentKey: string): Promise<ApiTradingAgentDates> {
  const response = await apiClient.get<ApiTradingAgentDates>(
    ENDPOINTS.admin.tradingAgentDates(agentKey),
  )
  return response.data
}

/** 指定日交易计划（缺省 trade_date 时后端取最近交易日；含下一交易日执行语义）。 */
export async function fetchTradingAgentPlans(
  agentKey: string,
  tradeDate?: string,
): Promise<ApiTradingAgentPlansResponse> {
  const response = await apiClient.get<ApiTradingAgentPlansResponse>(
    ENDPOINTS.admin.tradingAgentPlans(agentKey),
    { params: tradeDate ? { trade_date: tradeDate } : undefined },
  )
  return response.data
}

/** 人工取消当日 active 计划（triggered 后不可取消）。 */
export async function cancelTradingAgentPlan(
  agentKey: string,
  planId: number,
): Promise<ApiTradingAgentPlan> {
  const response = await apiClient.post<ApiTradingAgentPlan>(
    ENDPOINTS.admin.tradingAgentPlanCancel(agentKey, planId),
  )
  return response.data
}

/** agent 自选分组（null = 尚未生成选股）。 */
export async function fetchTradingAgentSelections(
  agentKey: string,
): Promise<ApiAgentWatchlistGroupResponse | null> {
  const response = await apiClient.get<ApiAgentWatchlistGroupResponse | null>(
    ENDPOINTS.admin.tradingAgentSelections(agentKey),
  )
  return response.data
}

/** 人工移出 agent 选股（全局生效，次日不重复选入）。 */
export async function removeTradingAgentSelection(
  agentKey: string,
  selectionId: number,
): Promise<void> {
  await apiClient.delete(ENDPOINTS.admin.tradingAgentSelection(agentKey, selectionId))
}

/** agent 记忆清单（缺省全部状态，按新近度倒序）。 */
export async function fetchTradingAgentMemories(
  agentKey: string,
  status?: 'active' | 'archived',
): Promise<ApiAgentMemory[]> {
  const response = await apiClient.get<ApiAgentMemory[]>(
    ENDPOINTS.admin.tradingAgentMemories(agentKey),
    { params: status ? { status } : undefined },
  )
  return response.data
}

/** 编辑记忆（标题/正文/类型，未提供字段不变）。 */
export async function updateTradingAgentMemory(
  agentKey: string,
  memoryId: number,
  data: ApiAgentMemoryUpdateRequest,
): Promise<ApiAgentMemory> {
  const response = await apiClient.put<ApiAgentMemory>(
    ENDPOINTS.admin.tradingAgentMemory(agentKey, memoryId),
    data,
  )
  return response.data
}

/** 切换记忆 active/archived（停用后次日计划 prompt 不再注入）。 */
export async function updateTradingAgentMemoryStatus(
  agentKey: string,
  memoryId: number,
  status: 'active' | 'archived',
): Promise<ApiAgentMemory> {
  const response = await apiClient.put<ApiAgentMemory>(
    ENDPOINTS.admin.tradingAgentMemoryStatus(agentKey, memoryId),
    { status },
  )
  return response.data
}

export type { AgentMemoryType }
