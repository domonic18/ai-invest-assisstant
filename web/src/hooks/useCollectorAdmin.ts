import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  fetchCollectorLogs,
  fetchCollectorTaskChannels,
  runCollectorTask,
} from '@/api/collectorAdmin'
import { mapCollectorLog } from '@/api/mappers'
import type {
  ApiCollectorTaskRunRequest,
  CollectorTaskName,
} from '@ai-invest/shared'

import { queryKeys } from './queryKeys'

const IN_FLIGHT_STATUSES = new Set(['pending', 'running'])

export function useCollectorLogs(limit = 50) {
  return useQuery({
    queryKey: [...queryKeys.collector.logs, limit],
    queryFn: async () => {
      const data = await fetchCollectorLogs(limit)
      return data.map(mapCollectorLog)
    },
    refetchInterval: (query) =>
      query.state.data?.some((log) => IN_FLIGHT_STATUSES.has(log.status)) ? 3000 : false,
  })
}

export function useCollectorTaskChannels(taskName: CollectorTaskName | null) {
  return useQuery({
    queryKey: queryKeys.collector.taskChannels(taskName ?? ''),
    queryFn: async () => fetchCollectorTaskChannels(taskName!),
    enabled: !!taskName,
  })
}

export function useRunCollectorTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      taskName,
      body,
    }: {
      taskName: CollectorTaskName
      body?: ApiCollectorTaskRunRequest
    }) => runCollectorTask(taskName, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.collector.logs })
    },
  })
}
