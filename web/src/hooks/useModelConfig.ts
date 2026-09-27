import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createLLMConfig,
  deleteLLMConfig,
  fetchAsrConfig,
  fetchLLMConfigs,
  setDefaultLLMConfig,
  testAsrConfig,
  testLLMConfig,
  updateAsrConfig,
  updateLLMConfig,
} from '@/api/modelConfig'
import { mapLLMConfig } from '@/api/mappers'
import type {
  ApiAsrConfigUpdateRequest,
  ApiLLMConfigCreateRequest,
  ApiLLMConfigUpdateRequest,
} from '@ai-invest/shared'

import { queryKeys } from '@/hooks/queryKeys'

const LLM_CONFIGS_KEY = queryKeys.llmConfigs

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

// ---- ASR 渠道 ----

const ASR_KEY = queryKeys.modelConfig.asr

export function useAsrConfig() {
  return useQuery({
    queryKey: ASR_KEY,
    queryFn: fetchAsrConfig,
  })
}

export function useUpdateAsrConfig() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ApiAsrConfigUpdateRequest) => updateAsrConfig(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ASR_KEY }),
  })
}

export function useTestAsrConfig() {
  return useMutation({
    mutationFn: () => testAsrConfig(),
  })
}
