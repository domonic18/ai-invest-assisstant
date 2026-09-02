import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { addWatchlistItem, fetchWatchlist, removeWatchlistItem } from '@/api/users'

import { queryKeys } from './queryKeys'

export function useWatchlist() {
  return useQuery({
    queryKey: queryKeys.watchlist.items,
    queryFn: fetchWatchlist,
  })
}

export function useAddWatchlistItem() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: addWatchlistItem,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.watchlist.all })
      queryClient.invalidateQueries({ queryKey: queryKeys.market.watchlistQuotes })
    },
  })
}

export function useRemoveWatchlistItem() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: removeWatchlistItem,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.watchlist.all })
      queryClient.invalidateQueries({ queryKey: queryKeys.market.watchlistQuotes })
    },
  })
}
