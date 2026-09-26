/** 交易 Agent hooks（admin，总览 + 配置 + 复盘查询 + 计划查询/取消，按 agentKey）。 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { message } from 'antd'

import type {
  AgentOverviewResponse,
  ApiAgentMemoryUpdateRequest,
  TradingAgentCreateRequest,
  TradingAgentProfileUpdateRequest,
  TradingReviewPeriod,
} from '@ai-invest/shared'

import { fetchLLMConfigs } from '@/api/modelConfig'
import {
  cancelTradingAgentPlan,
  createTradingAgent,
  deleteTradingAgent,
  fetchAgentOverview,
  fetchTradingAgentConfig,
  fetchTradingAgentDates,
  fetchTradingAgentMemories,
  fetchTradingAgentPlans,
  fetchTradingAgentPromptTemplates,
  fetchTradingAgentReview,
  fetchTradingAgentSelections,
  fetchTradingAgentStatus,
  removeTradingAgentSelection,
  updateTradingAgentConfig,
  updateTradingAgentMemory,
  updateTradingAgentMemoryStatus,
} from '@/api/tradingAgent'
import { queryKeys } from '@/hooks/queryKeys'

/** 全部注册 Agent 的总览聚合（贾维斯总览页传 refetchInterval 轮询）。 */
export function useAgentOverview(options?: { refetchInterval?: number | false }) {
  return useQuery({
    queryKey: queryKeys.tradingAgent.agents,
    queryFn: fetchAgentOverview,
    refetchInterval: options?.refetchInterval,
  })
}

/** Agent 能力/状态视图（工作台右栏，30s 轮询保持活动/任务新鲜）。 */
export function useTradingAgentStatus(
  agentKey: string,
  options?: { refetchInterval?: number | false },
) {
  return useQuery({
    queryKey: queryKeys.tradingAgent.status(agentKey),
    queryFn: () => fetchTradingAgentStatus(agentKey),
    refetchInterval: options?.refetchInterval,
  })
}

/** 可用会话人设模板清单（新建 Agent 下拉）。 */
export function useTradingAgentPromptTemplates() {
  return useQuery({
    queryKey: queryKeys.tradingAgent.templates,
    queryFn: fetchTradingAgentPromptTemplates,
    staleTime: 5 * 60 * 1000,
  })
}

/** 新建 Agent（创建即 active；成功后整体刷新注册表/总览/雷达）。 */
export function useCreateTradingAgent() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: TradingAgentCreateRequest) => createTradingAgent(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.tradingAgent.all })
      message.success('Agent 已创建并启用（绑定模拟盘账户后才会实际下单）')
    },
    onError: (error: Error) => message.error(error.message),
  })
}

/** 删除 Agent（级联清理其计划/选股/记忆/会话并解绑账户）。 */
export function useDeleteTradingAgent() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (agentKey: string) => deleteTradingAgent(agentKey),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.tradingAgent.all })
      message.success('Agent 已删除')
    },
    onError: (error: Error) => message.error(error.message),
  })
}

export function useTradingAgentConfig(agentKey: string) {
  return useQuery({
    queryKey: queryKeys.tradingAgent.config(agentKey),
    queryFn: () => fetchTradingAgentConfig(agentKey),
  })
}

/** 已生成的分层复盘（只读缓存，404 视为「尚未生成」由调用方处理）。 */
export function useTradingAgentReview(
  agentKey: string,
  period: TradingReviewPeriod,
  tradeDate?: string,
) {
  return useQuery({
    queryKey: queryKeys.tradingAgent.review(agentKey, period, tradeDate),
    queryFn: () => fetchTradingAgentReview(agentKey, period, tradeDate),
    retry: (failureCount, error) => {
      const status = (error as { response?: { status?: number } }).response?.status
      return status !== 404 && failureCount < 2
    },
  })
}

/** 有记录日期清单（计划/复盘日历打点，5 分钟档）。 */
export function useTradingAgentDates(agentKey: string) {
  return useQuery({
    queryKey: queryKeys.tradingAgent.dates(agentKey),
    queryFn: () => fetchTradingAgentDates(agentKey),
    staleTime: 5 * 60 * 1000,
  })
}

/** 交易 Agent 可绑定的对话模型选项（启用中的 chat 用途配置；留空 = 平台默认）。 */
export function useTradingAgentLlmOptions() {
  return useQuery({
    queryKey: queryKeys.tradingAgent.llmConfigs,
    queryFn: fetchLLMConfigs,
    select: (configs) =>
      configs
        .filter((config) => config.purpose === 'chat' && config.isActive)
        .map((config) => ({
          value: config.id,
          label: `${config.name}（${config.modelName}）${config.isDefault ? ' · 平台默认' : ''}`,
        })),
  })
}

export function useUpdateTradingAgentConfig(agentKey: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: TradingAgentProfileUpdateRequest) =>
      updateTradingAgentConfig(agentKey, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.tradingAgent.all })
      message.success('交易 Agent 配置已保存')
    },
    onError: (error: Error) => message.error(error.message),
  })
}

/** 指定日交易计划（缺省取最近交易日；含全部状态由前端分色）。 */
export function useTradingAgentPlans(agentKey: string, tradeDate?: string) {
  return useQuery({
    queryKey: queryKeys.tradingAgent.plans(agentKey, tradeDate),
    queryFn: () => fetchTradingAgentPlans(agentKey, tradeDate),
  })
}

/** 人工取消 active 计划（triggered 后端拒绝）。 */
export function useCancelTradingAgentPlan(agentKey: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (planId: number) => cancelTradingAgentPlan(agentKey, planId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.tradingAgent.all })
      message.success('计划已取消')
    },
    onError: (error: Error) => message.error(error.message),
  })
}

/** agent 自选分组（null = 尚未生成选股）。 */
export function useTradingAgentSelections(agentKey: string) {
  return useQuery({
    queryKey: queryKeys.tradingAgent.selections(agentKey),
    queryFn: () => fetchTradingAgentSelections(agentKey),
  })
}

/** 人工移出 agent 选股（removed_reason=manual，全局生效次日不重复选入）。 */
export function useRemoveTradingAgentSelection(agentKey: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (selectionId: number) => removeTradingAgentSelection(agentKey, selectionId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.tradingAgent.selections(agentKey) })
      message.success('已移出，次日不再选入')
    },
    onError: (error: Error) => message.error(error.message),
  })
}

/** agent 记忆清单（缺省全部状态，按新近度倒序）。 */
export function useTradingAgentMemories(agentKey: string) {
  return useQuery({
    queryKey: queryKeys.tradingAgent.memories(agentKey),
    queryFn: () => fetchTradingAgentMemories(agentKey),
  })
}

/** 编辑记忆（标题/正文/类型）。 */
export function useUpdateTradingAgentMemory(agentKey: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ memoryId, data }: { memoryId: number; data: ApiAgentMemoryUpdateRequest }) =>
      updateTradingAgentMemory(agentKey, memoryId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.tradingAgent.memories(agentKey) })
      message.success('记忆已保存')
    },
    onError: (error: Error) => message.error(error.message),
  })
}

/** 切换记忆 active/archived（停用后次日计划 prompt 不再注入）。 */
export function useUpdateTradingAgentMemoryStatus(agentKey: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ memoryId, status }: { memoryId: number; status: 'active' | 'archived' }) =>
      updateTradingAgentMemoryStatus(agentKey, memoryId, status),
    onSuccess: (_, vars) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.tradingAgent.memories(agentKey) })
      message.success(vars.status === 'active' ? '记忆已启用' : '记忆已停用，次日不再注入')
    },
    onError: (error: Error) => message.error(error.message),
  })
}

export type { AgentOverviewResponse }
