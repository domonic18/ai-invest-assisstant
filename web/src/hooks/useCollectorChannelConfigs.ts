import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createCollectorChannelConfig,
  deleteCollectorChannelConfig,
  fetchCollectorChannelConfigs,
  updateCollectorChannelConfig,
} from '@/api/collectorChannelConfig'
import { mapCollectorChannelConfig } from '@/api/mappers'
import type {
  ApiCollectorChannelConfigCreateRequest,
  ApiCollectorChannelConfigUpdateRequest,
} from '@ai-invest/shared'

const COLLECTOR_CHANNELS_KEY = ['collector-channel-configs'] as const

export function useCollectorChannelConfigs() {
  return useQuery({
    queryKey: COLLECTOR_CHANNELS_KEY,
    queryFn: async () => {
      const data = await fetchCollectorChannelConfigs()
      return data.map(mapCollectorChannelConfig)
    },
  })
}

export function useCreateCollectorChannelConfig() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ApiCollectorChannelConfigCreateRequest) =>
      createCollectorChannelConfig(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: COLLECTOR_CHANNELS_KEY }),
  })
}

export function useUpdateCollectorChannelConfig() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ApiCollectorChannelConfigUpdateRequest }) =>
      updateCollectorChannelConfig(id, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: COLLECTOR_CHANNELS_KEY }),
  })
}

export function useDeleteCollectorChannelConfig() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteCollectorChannelConfig(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: COLLECTOR_CHANNELS_KEY }),
  })
}
