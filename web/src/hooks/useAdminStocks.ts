import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createAdminStock,
  deleteAdminStock,
  fetchAdminStocks,
  updateAdminStock,
  type AdminStockParams,
} from '@/api/adminStocks'
import type {
  ApiAdminStockCreateRequest,
  ApiAdminStockUpdateRequest,
} from '@ai-invest/shared'

const ADMIN_STOCKS_KEY = ['admin-stocks'] as const

export function useAdminStocks(params: AdminStockParams = {}) {
  return useQuery({
    queryKey: [...ADMIN_STOCKS_KEY, params],
    queryFn: () => fetchAdminStocks(params),
  })
}

export function useCreateAdminStock() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ApiAdminStockCreateRequest) => createAdminStock(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ADMIN_STOCKS_KEY }),
  })
}

export function useUpdateAdminStock() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ApiAdminStockUpdateRequest }) => updateAdminStock(id, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ADMIN_STOCKS_KEY }),
  })
}

export function useDeleteAdminStock() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteAdminStock(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ADMIN_STOCKS_KEY }),
  })
}
