/** 交易 Agent hooks（admin，配置 + 复盘查询 + 计划查询/取消）。 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { message } from 'antd'

import type {
  ApiAgentMemoryUpdateRequest,
  ApiTradingAgentConfigUpdateRequest,
  TradingReviewPeriod,
} from '@ai-invest/shared'

import { fetchLLMConfigs } from '@/api/modelConfig'
import {
  cancelTradingAgentPlan,
  fetchTradingAgentConfig,
  fetchTradingAgentDates,
  fetchTradingAgentMemories,
  fetchTradingAgentPlans,
  fetchTradingAgentReview,
  fetchTradingAgentSelections,
  removeTradingAgentSelection,
  updateTradingAgentConfig,
  updateTradingAgentMemory,
  updateTradingAgentMemoryStatus,
} from '@/api/tradingAgent'
import { queryKeys } from '@/hooks/queryKeys'

export function useTradingAgentConfig() {
  return useQuery({
    queryKey: queryKeys.tradingAgent.config,
    queryFn: fetchTradingAgentConfig,
  })
}

/** 已生成的分层复盘（只读缓存，404 视为「尚未生成」由调用方处理）。 */
export function useTradingAgentReview(period: TradingReviewPeriod, tradeDate?: string) {
  return useQuery({
    queryKey: queryKeys.tradingAgent.review(period, tradeDate),
    queryFn: () => fetchTradingAgentReview(period, tradeDate),
    retry: (failureCount, error) => {
      const status = (error as { response?: { status?: number } }).response?.status
      return status !== 404 && failureCount < 2
    },
  })
}

/** 有记录日期清单（计划/复盘日历打点，5 分钟档）。 */
export function useTradingAgentDates() {
  return useQuery({
    queryKey: queryKeys.tradingAgent.dates,
    queryFn: fetchTradingAgentDates,
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

export function useUpdateTradingAgentConfig() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ApiTradingAgentConfigUpdateRequest) =>
      updateTradingAgentConfig(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.tradingAgent.all })
      message.success('交易 Agent 配置已保存')
    },
    onError: (error: Error) => message.error(error.message),
  })
}

/** 指定日交易计划（缺省取最近交易日；含全部状态由前端分色）。 */
export function useTradingAgentPlans(tradeDate?: string) {
  return useQuery({
    queryKey: queryKeys.tradingAgent.plans(tradeDate),
    queryFn: () => fetchTradingAgentPlans(tradeDate),
  })
}

/** 人工取消 active 计划（triggered 后端拒绝）。 */
export function useCancelTradingAgentPlan() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (planId: number) => cancelTradingAgentPlan(planId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.tradingAgent.all })
      message.success('计划已取消')
    },
    onError: (error: Error) => message.error(error.message),
  })
}

/** agent 自选分组（null = 尚未生成选股）。 */
export function useTradingAgentSelections() {
  return useQuery({
    queryKey: queryKeys.tradingAgent.selections,
    queryFn: fetchTradingAgentSelections,
  })
}

/** 人工移出 agent 选股（removed_reason=manual，全局生效次日不重复选入）。 */
export function useRemoveTradingAgentSelection() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (selectionId: number) => removeTradingAgentSelection(selectionId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.tradingAgent.selections })
      message.success('已移出，次日不再选入')
    },
    onError: (error: Error) => message.error(error.message),
  })
}

/** agent 记忆清单（缺省全部状态，按新近度倒序）。 */
export function useTradingAgentMemories() {
  return useQuery({
    queryKey: queryKeys.tradingAgent.memories,
    queryFn: () => fetchTradingAgentMemories(),
  })
}

/** 编辑记忆（标题/正文/类型）。 */
export function useUpdateTradingAgentMemory() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ memoryId, data }: { memoryId: number; data: ApiAgentMemoryUpdateRequest }) =>
      updateTradingAgentMemory(memoryId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.tradingAgent.memories })
      message.success('记忆已保存')
    },
    onError: (error: Error) => message.error(error.message),
  })
}

/** 切换记忆 active/archived（停用后次日计划 prompt 不再注入）。 */
export function useUpdateTradingAgentMemoryStatus() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ memoryId, status }: { memoryId: number; status: 'active' | 'archived' }) =>
      updateTradingAgentMemoryStatus(memoryId, status),
    onSuccess: (_, vars) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.tradingAgent.memories })
      message.success(vars.status === 'active' ? '记忆已启用' : '记忆已停用，次日不再注入')
    },
    onError: (error: Error) => message.error(error.message),
  })
}
