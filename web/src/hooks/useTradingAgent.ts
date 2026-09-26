/** 交易 Agent hooks（admin，配置 + 复盘查询 + 计划查询/取消）。 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { message } from 'antd'

import type {
  ApiTradingAgentConfigUpdateRequest,
  TradingReviewPeriod,
} from '@ai-invest/shared'

import { fetchLLMConfigs } from '@/api/modelConfig'
import {
  cancelTradingAgentPlan,
  fetchTradingAgentConfig,
  fetchTradingAgentPlans,
  fetchTradingAgentReview,
  updateTradingAgentConfig,
} from '@/api/tradingAgent'
import { queryKeys } from '@/hooks/queryKeys'

export function useTradingAgentConfig() {
  return useQuery({
    queryKey: queryKeys.tradingAgent.config,
    queryFn: fetchTradingAgentConfig,
  })
}

/** 已生成的分层复盘（只读缓存，404 视为「尚未生成」由调用方处理）。 */
export function useTradingAgentReview(period: TradingReviewPeriod) {
  return useQuery({
    queryKey: queryKeys.tradingAgent.review(period),
    queryFn: () => fetchTradingAgentReview(period),
    retry: (failureCount, error) => {
      const status = (error as { response?: { status?: number } }).response?.status
      return status !== 404 && failureCount < 2
    },
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
