import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiPasswordChangeRequest,
  ApiUserResponse,
  ApiWatchlistBatchItemCreate,
  ApiWatchlistBatchResponse,
  ApiWatchlistGroupCreate,
  ApiWatchlistGroupReorderRequest,
  ApiWatchlistGroupUpdate,
  ApiWatchlistGroupWithItemsResponse,
  ApiWatchlistItemResponse,
  ApiWatchlistScreenshotRecognitionResponse,
} from '@ai-invest/shared'
import type { User } from '@ai-invest/shared'

import { apiClient } from './client'
import { mapUser, mapWatchlistGroup, mapWatchlistItem } from './mappers'

export interface WatchlistCreateData {
  stockCode: string
  tags?: string[]
  groupId?: number
}

export async function fetchWatchlist() {
  const response = await apiClient.get<ApiWatchlistItemResponse[]>(ENDPOINTS.users.watchlist)
  return response.data.map(mapWatchlistItem)
}

/** 当前用户资料（含注册时间/上次登录等 wire 全量字段，供设置页展示）。 */
export interface MyProfile {
  id: number
  username: string
  email: string
  role: string
  isActive: boolean
  lastLoginAt: string | null
  createdAt: string
}

export async function fetchMyProfile(): Promise<MyProfile> {
  const response = await apiClient.get<ApiUserResponse>(ENDPOINTS.users.me)
  return response.data
}

export async function updateMyEmail(email: string): Promise<User> {
  const response = await apiClient.put<ApiUserResponse>(ENDPOINTS.users.me, { email })
  return mapUser(response.data)
}

export async function changeMyPassword(data: ApiPasswordChangeRequest): Promise<void> {
  await apiClient.post(ENDPOINTS.users.mePassword, data)
}

export async function addWatchlistItem(data: WatchlistCreateData) {
  const response = await apiClient.post<ApiWatchlistItemResponse>(ENDPOINTS.users.watchlist, {
    stockCode: data.stockCode,
    tags: data.tags,
    groupId: data.groupId,
  })
  return mapWatchlistItem(response.data)
}

export async function removeWatchlistItem(id: string) {
  await apiClient.delete(ENDPOINTS.users.watchlistItem(id))
}

export async function moveWatchlistItem(id: string, groupId: number) {
  const response = await apiClient.patch<ApiWatchlistItemResponse>(
    ENDPOINTS.users.watchlistItem(id),
    { groupId },
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

export async function deleteWatchlistGroup(
  groupId: number,
  options: { deleteItems?: boolean } = {},
) {
  await apiClient.delete(ENDPOINTS.users.watchlistGroup(groupId), {
    params: { delete_items: options.deleteItems ?? false },
  })
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
    stockCode: item.stockCode,
    stockName: item.stockName,
    confidence: item.confidence,
    valid: item.valid,
    matchedName: item.matchedName,
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
    groupId: groupId,
    newGroupName: newGroupName,
  })
  return {
    created: response.data.created.length,
    duplicated: response.data.duplicated.map((d) => ({
      stockCode: d.stockCode,
      groupName: d.groupName,
    })),
    invalid: response.data.invalid,
  }
}
