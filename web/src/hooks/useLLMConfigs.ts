import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createLLMConfig,
  deleteLLMConfig,
  fetchLLMConfigs,
  setDefaultLLMConfig,
  testLLMConfig,
  updateLLMConfig,
} from '@/api/llmConfig'
import { mapLLMConfig } from '@/api/mappers'
import type {
  ApiLLMConfigCreateRequest,
  ApiLLMConfigUpdateRequest,
} from '@ai-invest/shared'

const LLM_CONFIGS_KEY = ['llm-configs'] as const

export function useLLMConfigs() {
  return useQuery({
    queryKey: LLM_CONFIGS_KEY,
    queryFn: async () => {
      const data = await fetchLLMConfigs()
      return data.map(mapLLMConfig)
    },
  })
}

export function useCreateLLMConfig() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ApiLLMConfigCreateRequest) => createLLMConfig(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: LLM_CONFIGS_KEY }),
  })
}

export function useUpdateLLMConfig() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ApiLLMConfigUpdateRequest }) =>
      updateLLMConfig(id, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: LLM_CONFIGS_KEY }),
  })
}

export function useDeleteLLMConfig() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteLLMConfig(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: LLM_CONFIGS_KEY }),
  })
}

export function useSetDefaultLLMConfig() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => setDefaultLLMConfig(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: LLM_CONFIGS_KEY }),
  })
}

export function useTestLLMConfig() {
  return useMutation({
    mutationFn: (id: number) => testLLMConfig(id),
  })
}
