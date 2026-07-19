import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  fetchCollectorDataTypes,
  replaceDataTypeChannels,
} from '@/api/collectorDataTypes'
import { mapCollectorDataTypeChannels } from '@/api/mappers'
import type { ApiDataTypeChannelPriorityInput } from '@ai-invest/shared'

const COLLECTOR_DATA_TYPES_KEY = ['collector-data-type-channels'] as const

export function useCollectorDataTypeChannels() {
  return useQuery({
    queryKey: COLLECTOR_DATA_TYPES_KEY,
    queryFn: async () => {
      const data = await fetchCollectorDataTypes()
      return data.map(mapCollectorDataTypeChannels)
    },
  })
}

export function useReplaceDataTypeChannels() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      dataType,
      items,
    }: {
      dataType: string
      items: ApiDataTypeChannelPriorityInput[]
    }) => replaceDataTypeChannels(dataType, items),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: COLLECTOR_DATA_TYPES_KEY })
      // supported_data_types 冗余缓存也被回写，渠道列表需同步刷新
      queryClient.invalidateQueries({ queryKey: ['collector-channel-configs'] })
    },
  })
}
