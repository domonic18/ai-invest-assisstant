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

const COLLECTOR_LOGS_KEY = ['collector-logs'] as const

export function useCollectorLogs(limit = 50) {
  return useQuery({
    queryKey: [...COLLECTOR_LOGS_KEY, limit],
    queryFn: async () => {
      const data = await fetchCollectorLogs(limit)
      return data.map(mapCollectorLog)
    },
  })
}

export function useCollectorTaskChannels(taskName: CollectorTaskName | null) {
  return useQuery({
    queryKey: ['collector-task-channels', taskName],
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
      queryClient.invalidateQueries({ queryKey: COLLECTOR_LOGS_KEY })
    },
  })
}
