import { useQuery } from '@tanstack/react-query'

import { fetchSystemStatus } from '@/api/adminSystemStatus'
import { queryKeys } from '@/hooks/queryKeys'

const REFRESH_INTERVAL_MS = 30_000

export function useSystemStatus() {
  return useQuery({
    queryKey: queryKeys.admin.systemStatus,
    queryFn: fetchSystemStatus,
    refetchInterval: REFRESH_INTERVAL_MS,
    staleTime: REFRESH_INTERVAL_MS / 2,
  })
}
