import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  batchDeleteAdminTelegraph,
  deleteAdminTelegraph,
  fetchAdminTelegraph,
  type AdminTelegraphParams,
} from '@/api/adminTelegraph'
import { queryKeys } from '@/hooks/queryKeys'

const ADMIN_TELEGRAPH_KEY = queryKeys.admin.telegraph

export function useAdminTelegraph(params: AdminTelegraphParams = {}) {
  return useQuery({
    queryKey: [...ADMIN_TELEGRAPH_KEY, params],
    queryFn: () => fetchAdminTelegraph(params),
  })
}

export function useDeleteAdminTelegraph() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteAdminTelegraph(id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ADMIN_TELEGRAPH_KEY }),
  })
}

export function useBatchDeleteAdminTelegraph() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (ids: number[]) => batchDeleteAdminTelegraph(ids),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ADMIN_TELEGRAPH_KEY }),
  })
}
