import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  clearHealthSnapshots,
  fetchHealthChannels,
  fetchHealthOverview,
  fetchHealthScheduleCheck,
  fetchHealthTasks,
  runHealthCheck,
  type HealthTaskFilters,
} from '@/api/collectorHealth'

import { queryKeys } from './queryKeys'

export function useCollectorHealthOverview(options?: { refetchInterval?: number }) {
  return useQuery({
    queryKey: queryKeys.collector.healthOverview,
    queryFn: fetchHealthOverview,
    staleTime: 60 * 1000,
    refetchInterval: options?.refetchInterval,
  })
}

export function useCollectorHealthTasks(filters: HealthTaskFilters) {
  const domain = filters.domain ?? null
  const status = filters.status ?? null
  return useQuery({
    queryKey: queryKeys.collector.healthTasks(domain, status),
    queryFn: () => fetchHealthTasks({ domain, status }),
    placeholderData: keepPreviousData,
  })
}

export function useCollectorHealthChannels() {
  return useQuery({
    queryKey: queryKeys.collector.healthChannels,
    queryFn: fetchHealthChannels,
    staleTime: 60 * 1000,
  })
}

export function useCollectorHealthScheduleCheck(date: string | null) {
  return useQuery({
    queryKey: queryKeys.collector.healthScheduleCheck(date ?? ''),
    queryFn: () => fetchHealthScheduleCheck(date!),
    enabled: !!date,
    placeholderData: keepPreviousData,
  })
}

export function useRunHealthCheck() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: runHealthCheck,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.collector.healthAll })
    },
  })
}

export function useClearHealthSnapshots() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => clearHealthSnapshots(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.collector.healthAll })
    },
  })
}

/** 侧边栏角标：轮询总览快照，返回 critical+silent 故障数（读小表，开销可忽略）。 */
export function useCollectorHealthBadgeCount(enabled: boolean) {
  const { data } = useCollectorHealthOverview({ refetchInterval: 300 * 1000 })
  if (!enabled || !data) return 0
  return data.counts.critical + data.counts.silent
}
