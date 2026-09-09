import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createProxyConfig,
  deleteProxyConfig,
  fetchProxyConfigs,
  testProxyConfig,
  updateProxyConfig,
} from '@/api/proxyConfig'
import { mapProxyConfig } from '@/api/mappers'
import type {
  ApiProxyConfigCreateRequest,
  ApiProxyConfigUpdateRequest,
} from '@ai-invest/shared'

import { queryKeys } from '@/hooks/queryKeys'

const PROXY_CONFIGS_KEY = queryKeys.proxyConfigs

export function useProxyConfigs() {
  return useQuery({
    queryKey: PROXY_CONFIGS_KEY,
    queryFn: async () => {
      const data = await fetchProxyConfigs()
      return data.map(mapProxyConfig)
    },
  })
}

export function useCreateProxyConfig() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ApiProxyConfigCreateRequest) => createProxyConfig(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: PROXY_CONFIGS_KEY }),
  })
}

export function useUpdateProxyConfig() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ApiProxyConfigUpdateRequest }) =>
      updateProxyConfig(id, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: PROXY_CONFIGS_KEY }),
  })
}

export function useDeleteProxyConfig() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteProxyConfig(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: PROXY_CONFIGS_KEY }),
  })
}

export function useTestProxyConfig() {
  return useMutation({
    mutationFn: (id: number) => testProxyConfig(id),
  })
}
