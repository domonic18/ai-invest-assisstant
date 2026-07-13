import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { addWatchlistItem, fetchWatchlist, removeWatchlistItem } from '@/api/users'

const WATCHLIST_KEY = 'watchlist'

export function useWatchlist() {
  return useQuery({
    queryKey: [WATCHLIST_KEY],
    queryFn: fetchWatchlist,
  })
}

export function useAddWatchlistItem() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: addWatchlistItem,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [WATCHLIST_KEY] })
    },
  })
}

export function useRemoveWatchlistItem() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: removeWatchlistItem,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [WATCHLIST_KEY] })
    },
  })
}
