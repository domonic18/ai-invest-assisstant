import { useQuery } from '@tanstack/react-query'

import { fetchCeleryQueues } from '@/api/adminSystemStatus'
import { queryKeys } from '@/hooks/queryKeys'

const RUNNING_POLL_MS = 3_000
const IDLE_POLL_MS = 10_000

export function useCeleryQueues() {
  return useQuery({
    queryKey: queryKeys.admin.celeryQueues,
    queryFn: fetchCeleryQueues,
    refetchInterval: (query) => {
      const queues = query.state.data?.queues
      const hasRunning = queues?.some((q) => q.tasks.some((t) => t.state === 'running'))
      return hasRunning ? RUNNING_POLL_MS : IDLE_POLL_MS
    },
    staleTime: 2_500,
  })
}
