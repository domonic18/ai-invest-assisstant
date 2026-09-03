import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { ApiWatchlistGroupCreate, ApiWatchlistGroupUpdate } from '@ai-invest/shared'

import {
  createWatchlistGroup,
  deleteWatchlistGroup,
  fetchWatchlistGroups,
  moveWatchlistItem,
  reorderWatchlistGroups,
  updateWatchlistGroup,
} from '@/api/users'

import { queryKeys } from './queryKeys'

const GROUPS_KEY = queryKeys.watchlist.groups

/** 分组/自选股任何写操作后，组树、平铺列表与行情卡缓存一并失效。 */
export function useInvalidateWatchlist() {
  const queryClient = useQueryClient()
  return () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.watchlist.all })
    queryClient.invalidateQueries({ queryKey: queryKeys.market.watchlistQuotes })
  }
}

export function useWatchlistGroups() {
  return useQuery({
    queryKey: GROUPS_KEY,
    queryFn: fetchWatchlistGroups,
  })
}

export function useCreateWatchlistGroup() {
  const invalidate = useInvalidateWatchlist()
  return useMutation({
    mutationFn: (data: ApiWatchlistGroupCreate) => createWatchlistGroup(data),
    onSuccess: invalidate,
  })
}

export function useUpdateWatchlistGroup() {
  const invalidate = useInvalidateWatchlist()
  return useMutation({
    mutationFn: ({ groupId, data }: { groupId: number; data: ApiWatchlistGroupUpdate }) =>
      updateWatchlistGroup(groupId, data),
    onSuccess: invalidate,
  })
}

export function useDeleteWatchlistGroup() {
  const invalidate = useInvalidateWatchlist()
  return useMutation({
    mutationFn: (groupId: number) => deleteWatchlistGroup(groupId),
    onSuccess: invalidate,
  })
}

export function useReorderWatchlistGroups() {
  const invalidate = useInvalidateWatchlist()
  return useMutation({
    mutationFn: (groupIds: number[]) => reorderWatchlistGroups({ group_ids: groupIds }),
    onSuccess: invalidate,
  })
}

export function useMoveWatchlistItem() {
  const invalidate = useInvalidateWatchlist()
  return useMutation({
    mutationFn: ({ itemId, groupId }: { itemId: string; groupId: number }) =>
      moveWatchlistItem(itemId, groupId),
    onSuccess: invalidate,
  })
}

export function useToggleGroupAiReview() {
  const invalidate = useInvalidateWatchlist()
  return useMutation({
    mutationFn: ({ groupId, enabled }: { groupId: number; enabled: boolean }) =>
      updateWatchlistGroup(groupId, { ai_review_enabled: enabled }),
    onSuccess: invalidate,
  })
}
