import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  fetchCollectorDataTypes,
  replaceDataTypeChannels,
} from '@/api/collectorDataTypes'
import { mapCollectorDataTypeChannels } from '@/api/mappers'
import type { ApiDataTypeChannelPriorityInput } from '@ai-invest/shared'

import { queryKeys } from './queryKeys'

export function useCollectorDataTypeChannels() {
  return useQuery({
    queryKey: queryKeys.collector.dataTypes,
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
      queryClient.invalidateQueries({ queryKey: queryKeys.collector.dataTypes })
      // supported_data_types 冗余缓存也被回写，渠道列表需同步刷新
      queryClient.invalidateQueries({ queryKey: queryKeys.collector.channels })
    },
  })
}
