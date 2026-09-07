import { Client } from '@langchain/langgraph-sdk'

import { API_BASE, StorageKey } from '@ai-invest/shared'

import { apiClient } from './client'

export interface AssistantSessionItem {
  threadId: string
  title: string | null
  lastMessageAt: string | null
  createdAt: string
  updatedAt: string
}

export interface SessionListResponse {
  sessions: AssistantSessionItem[]
  total: number
}

export const fetchSessions = async (
  params?: { limit?: number; offset?: number },
): Promise<SessionListResponse> => {
  // axios baseURL 在生产构建下为空串，须走 shared 的全路径约定
  const { data } = await apiClient.get<SessionListResponse>(
    `${API_BASE}/assistant/sessions`,
    { params },
  )
  return data
}

export const deleteSession = async (threadId: string): Promise<void> => {
  await apiClient.delete(`${API_BASE}/assistant/threads/${threadId}`)
}

export const createAssistantClient = (): Client => {
  // langgraph-sdk 内部用 new URL(apiUrl + path) 拼接，必须传绝对地址
  const origin = typeof window !== 'undefined' ? window.location.origin : ''
  const token = localStorage.getItem(StorageKey.auth.accessToken)
  return new Client({
    apiUrl: `${origin}${API_BASE}/assistant`,
    apiKey: null,
    defaultHeaders: token ? { Authorization: `Bearer ${token}` } : undefined,
  })
}
