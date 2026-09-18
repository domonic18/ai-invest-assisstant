import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  fetchCollectorLogSummary,
  fetchCollectorLogs,
  fetchCollectorTaskCatalog,
  fetchCollectorTaskChannels,
  runCollectorTask,
  type CollectorLogFilters,
} from '@/api/collectorAdmin'
import { mapCollectorLog, mapCollectorTaskCatalog } from '@/api/mappers'
import { mapPaginatedResponse } from '@/api/mappers/common'
import type {
  ApiCollectorTaskRunRequest,
  CollectorTaskName,
} from '@ai-invest/shared'

import { registerTaskCatalogLabels } from '@/utils/collectorTaskLabels'

import { queryKeys } from './queryKeys'

const IN_FLIGHT_STATUSES = new Set(['pending', 'running'])
const IN_FLIGHT_POLL_MS = 3000

export function useCollectorTaskCatalog() {
  return useQuery({
    queryKey: queryKeys.collector.taskCatalog,
    queryFn: async () => {
      const data = await fetchCollectorTaskCatalog()
      // 目录是任务中文标签的唯一真相源，注册后全局 getTaskLabel 可查
      registerTaskCatalogLabels(data.items)
      return mapCollectorTaskCatalog(data)
    },
    staleTime: 5 * 60 * 1000,
  })
}

export function useCollectorLogs(filters: CollectorLogFilters = {}) {
  const params = {
    page: filters.page ?? 1,
    pageSize: filters.pageSize ?? 20,
    taskName: filters.taskName ?? null,
    source: filters.source ?? null,
    status: filters.status ?? null,
    startDate: filters.startDate ?? null,
    endDate: filters.endDate ?? null,
  }
  return useQuery({
    queryKey: [...queryKeys.collector.logs, params],
    queryFn: async () => {
      const data = await fetchCollectorLogs(params)
      return mapPaginatedResponse(data, mapCollectorLog)
    },
    refetchInterval: (query) =>
      query.state.data?.items.some((log) => IN_FLIGHT_STATUSES.has(log.status))
        ? IN_FLIGHT_POLL_MS
        : false,
  })
}

/** 今日（Asia/Shanghai）采集日志按状态计数；有运行中任务时 3s 轮询联动刷新。 */
export function useCollectorLogSummary() {
  return useQuery({
    queryKey: queryKeys.collector.logSummary,
    queryFn: fetchCollectorLogSummary,
    refetchInterval: IN_FLIGHT_POLL_MS,
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
