/** 交易 Agent 配置 hooks（admin）。 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { message } from 'antd'

import type { ApiTradingAgentConfigUpdateRequest } from '@ai-invest/shared'

import { fetchLLMConfigs } from '@/api/modelConfig'
import { fetchTradingAgentConfig, updateTradingAgentConfig } from '@/api/tradingAgent'
import { queryKeys } from '@/hooks/queryKeys'

export function useTradingAgentConfig() {
  return useQuery({
    queryKey: queryKeys.tradingAgent.config,
    queryFn: fetchTradingAgentConfig,
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
