import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createAdminStockConcept,
  deleteAdminStockConcept,
  fetchAdminStockConcepts,
  updateAdminStockConcept,
  type AdminStockConceptParams,
} from '@/api/adminStockConcepts'
import type {
  ApiAdminStockConceptCreateRequest,
  ApiAdminStockConceptUpdateRequest,
} from '@ai-invest/shared'

import { queryKeys } from '@/hooks/queryKeys'

const ADMIN_STOCK_CONCEPTS_KEY = queryKeys.admin.stockConcepts

export function useAdminStockConcepts(params: AdminStockConceptParams = {}) {
  return useQuery({
    queryKey: [...ADMIN_STOCK_CONCEPTS_KEY, params],
    queryFn: () => fetchAdminStockConcepts(params),
  })
}

export function useCreateAdminStockConcept() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ApiAdminStockConceptCreateRequest) =>
      createAdminStockConcept(data),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ADMIN_STOCK_CONCEPTS_KEY }),
  })
}

export function useUpdateAdminStockConcept() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: number
      data: ApiAdminStockConceptUpdateRequest
    }) => updateAdminStockConcept(id, data),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ADMIN_STOCK_CONCEPTS_KEY }),
  })
}

export function useDeleteAdminStockConcept() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteAdminStockConcept(id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ADMIN_STOCK_CONCEPTS_KEY }),
  })
}
