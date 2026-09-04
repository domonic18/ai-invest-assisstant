import { Client } from '@langchain/langgraph-sdk'

import { API_BASE } from '@ai-invest/shared'

import { apiClient } from './client'

export interface AssistantSessionItem {
  thread_id: string
  title: string | null
  last_message_at: string | null
  created_at: string
  updated_at: string
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
  const token = localStorage.getItem('access_token')
  return new Client({
    apiUrl: `${origin}${API_BASE}/assistant`,
    apiKey: null,
    defaultHeaders: token ? { Authorization: `Bearer ${token}` } : undefined,
  })
}
