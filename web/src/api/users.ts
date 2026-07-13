import { ENDPOINTS } from '@ai-invest/shared'
import type { ApiWatchlistItemResponse } from '@ai-invest/shared'

import { apiClient } from './client'
import { mapWatchlistItem } from './mappers'

export interface WatchlistCreateData {
  stockCode: string
  tags?: string[]
}

export async function fetchWatchlist() {
  const response = await apiClient.get<ApiWatchlistItemResponse[]>(ENDPOINTS.users.watchlist)
  return response.data.map(mapWatchlistItem)
}

export async function addWatchlistItem(data: WatchlistCreateData) {
  const response = await apiClient.post<ApiWatchlistItemResponse>(ENDPOINTS.users.watchlist, {
    stock_code: data.stockCode,
    tags: data.tags,
  })
  return mapWatchlistItem(response.data)
}

export async function removeWatchlistItem(id: string) {
  await apiClient.delete(`${ENDPOINTS.users.watchlist}/${id}`)
}
