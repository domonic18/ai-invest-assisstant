import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiWatchlistBatchItemCreate,
  ApiWatchlistBatchResponse,
  ApiWatchlistGroupCreate,
  ApiWatchlistGroupReorderRequest,
  ApiWatchlistGroupUpdate,
  ApiWatchlistGroupWithItemsResponse,
  ApiWatchlistItemResponse,
  ApiWatchlistScreenshotRecognitionResponse,
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

export interface WatchlistRecognizedItem {
  stockCode: string
  stockName: string | null
  confidence: number | null
  valid: boolean
  matchedName: string | null
}

export interface WatchlistBatchImportResult {
  created: number
  duplicated: Array<{ stockCode: string; groupName: string | null }>
  invalid: string[]
}

export async function recognizeWatchlistScreenshot(file: File): Promise<WatchlistRecognizedItem[]> {
  const form = new FormData()
  form.append('file', file)
  const response = await apiClient.post<ApiWatchlistScreenshotRecognitionResponse>(
    ENDPOINTS.users.watchlistRecognizeScreenshot,
    form,
  )
  return response.data.items.map((item) => ({
    stockCode: item.stock_code,
    stockName: item.stock_name,
    confidence: item.confidence,
    valid: item.valid,
    matchedName: item.matched_name,
  }))
}

export async function batchAddWatchlist(data: {
  items: ApiWatchlistBatchItemCreate[]
  groupId?: number
  newGroupName?: string
}): Promise<WatchlistBatchImportResult> {
  const { items, groupId, newGroupName } = data
  const response = await apiClient.post<ApiWatchlistBatchResponse>(ENDPOINTS.users.watchlistBatch, {
    items,
    group_id: groupId,
    new_group_name: newGroupName,
  })
  return {
    created: response.data.created.length,
    duplicated: response.data.duplicated.map((d) => ({
      stockCode: d.stock_code,
      groupName: d.group_name,
    })),
    invalid: response.data.invalid,
  }
}
