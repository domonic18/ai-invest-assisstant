import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createNewsSubscription,
  deleteNewsSubscription,
  fetchNewsSubscriptions,
  updateNewsSubscription,
} from '@/api/news'

import { queryKeys } from './queryKeys'

/** 我的订阅列表（含命中统计）。 */
export function useNewsSubscriptions() {
  return useQuery({
    queryKey: queryKeys.news.subscriptions,
    queryFn: fetchNewsSubscriptions,
  })
}

/** 订阅写操作后失效订阅列表与电报流（★ 标注/仅看命中会随之变化）。 */
function useInvalidateSubscriptions() {
  const queryClient = useQueryClient()
  return () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.news.subscriptions })
    queryClient.invalidateQueries({ queryKey: queryKeys.telegraph.all })
  }
}

export function useCreateNewsSubscription() {
  const invalidate = useInvalidateSubscriptions()
  return useMutation({
    mutationFn: (payload: { keyword: string; channels?: string[] | null }) =>
      createNewsSubscription(payload),
    onSuccess: invalidate,
  })
}

export function useUpdateNewsSubscription() {
  const invalidate = useInvalidateSubscriptions()
  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: number
      data: { channels?: string[] | null; pushEnabled?: boolean; enabled?: boolean }
    }) => updateNewsSubscription(id, data),
    onSuccess: invalidate,
  })
}

export function useDeleteNewsSubscription() {
  const invalidate = useInvalidateSubscriptions()
  return useMutation({
    mutationFn: (id: number) => deleteNewsSubscription(id),
    onSuccess: invalidate,
  })
}
