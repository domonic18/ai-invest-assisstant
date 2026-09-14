import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { ApiUserLlmConfigUpsertRequest } from '@ai-invest/shared'

import {
  clearMyLlmConfig,
  fetchMyLlmConfig,
  fetchMyQuota,
  fetchMyUsage,
  saveMyLlmConfig,
} from '@/api/account'
import { queryKeys } from '@/hooks/queryKeys'

export function useMyQuota() {
  return useQuery({
    queryKey: queryKeys.account.quota,
    queryFn: fetchMyQuota,
  })
}

export function useMyUsage(feature?: string) {
  return useQuery({
    queryKey: queryKeys.account.usage(feature),
    queryFn: () => fetchMyUsage(feature),
  })
}

export function useMyLlmConfig() {
  return useQuery({
    queryKey: queryKeys.account.llmConfig,
    queryFn: fetchMyLlmConfig,
  })
}

export function useSaveMyLlmConfig() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ApiUserLlmConfigUpsertRequest) => saveMyLlmConfig(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.account.llmConfig })
      queryClient.invalidateQueries({ queryKey: queryKeys.account.quota })
    },
  })
}

export function useClearMyLlmConfig() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => clearMyLlmConfig(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.account.llmConfig })
      queryClient.invalidateQueries({ queryKey: queryKeys.account.quota })
    },
  })
}
