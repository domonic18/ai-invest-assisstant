import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createAdminMarketReview,
  deleteAdminMarketReview,
  fetchAdminMarketReviews,
  updateAdminMarketReview,
  type AdminMarketReviewListParams,
} from '@/api/adminMarketReviews'
import { queryKeys } from '@/hooks/queryKeys'

export function useAdminMarketReviews(params: AdminMarketReviewListParams = {}) {
  return useQuery({
    queryKey: [...queryKeys.admin.marketReviews, params],
    queryFn: () => fetchAdminMarketReviews(params),
  })
}

export function useCreateAdminMarketReview() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: { tradeDate: string; sections: Record<string, string> }) =>
      createAdminMarketReview({ trade_date: data.tradeDate, sections: data.sections }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.marketReviews }),
  })
}

export function useUpdateAdminMarketReview() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      tradeDate,
      sections,
    }: { tradeDate: string; sections: Record<string, string> }) =>
      updateAdminMarketReview(tradeDate, { sections }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.marketReviews }),
  })
}

export function useDeleteAdminMarketReview() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (tradeDate: string) => deleteAdminMarketReview(tradeDate),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.marketReviews }),
  })
}
