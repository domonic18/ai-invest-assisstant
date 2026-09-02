import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiWatchlistGroupCreate,
  ApiWatchlistGroupReorderRequest,
  ApiWatchlistGroupUpdate,
  ApiWatchlistGroupWithItemsResponse,
  ApiWatchlistItemResponse,
} from '@ai-invest/shared'

import { apiClient } from './client'
import { mapWatchlistGroup, mapWatchlistItem } from './mappers'

export interface WatchlistCreateData {
  stockCode: string
  tags?: string[]
  groupId?: number
}

export async function fetchWatchlist() {
  const response = await apiClient.get<ApiWatchlistItemResponse[]>(ENDPOINTS.users.watchlist)
  return response.data.map(mapWatchlistItem)
}

export async function addWatchlistItem(data: WatchlistCreateData) {
  const response = await apiClient.post<ApiWatchlistItemResponse>(ENDPOINTS.users.watchlist, {
    stock_code: data.stockCode,
    tags: data.tags,
    group_id: data.groupId,
  })
  return mapWatchlistItem(response.data)
}

export async function removeWatchlistItem(id: string) {
  await apiClient.delete(ENDPOINTS.users.watchlistItem(id))
}

export async function moveWatchlistItem(id: string, groupId: number) {
  const response = await apiClient.patch<ApiWatchlistItemResponse>(
    ENDPOINTS.users.watchlistItem(id),
    { group_id: groupId },
  )
  return mapWatchlistItem(response.data)
}

export async function fetchWatchlistGroups() {
  const response = await apiClient.get<ApiWatchlistGroupWithItemsResponse[]>(
    ENDPOINTS.users.watchlistGroups,
  )
  return response.data.map(mapWatchlistGroup)
}

export async function createWatchlistGroup(data: ApiWatchlistGroupCreate) {
  const response = await apiClient.post<ApiWatchlistGroupWithItemsResponse>(
    ENDPOINTS.users.watchlistGroups,
    data,
  )
  return mapWatchlistGroup(response.data)
}

export async function updateWatchlistGroup(groupId: number, data: ApiWatchlistGroupUpdate) {
  const response = await apiClient.patch<ApiWatchlistGroupWithItemsResponse>(
    ENDPOINTS.users.watchlistGroup(groupId),
    data,
  )
  return mapWatchlistGroup(response.data)
}

export async function deleteWatchlistGroup(groupId: number) {
  await apiClient.delete(ENDPOINTS.users.watchlistGroup(groupId))
}

export async function reorderWatchlistGroups(data: ApiWatchlistGroupReorderRequest) {
  await apiClient.put(ENDPOINTS.users.watchlistGroupOrder, data)
}
