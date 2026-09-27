import { Client } from '@langchain/langgraph-sdk'

import { API_BASE, StorageKey } from '@ai-invest/shared'

import { apiClient } from './client'

// 后端 assistant 协议层对齐 langgraph-sdk 的 snake_case wire，勿改成 camelCase
/** 'assistant' = 人工助手；其余值为交易 Agent 的 agent_key（后端注册表校验）。 */
export type AssistantAgentType = string

export interface AssistantSessionItem {
  thread_id: string
  title: string | null
  agent_type?: AssistantAgentType
  last_message_at: string | null
  created_at: string
  updated_at: string
}

export interface SessionListResponse {
  sessions: AssistantSessionItem[]
  total: number
}

export interface ThreadResponse {
  thread_id: string
  title: string | null
  agent_type: AssistantAgentType
  last_message_at: string | null
  created_at: string
  updated_at: string
}

export const fetchSessions = async (
  params?: { limit?: number; offset?: number; agentType?: AssistantAgentType },
): Promise<SessionListResponse> => {
  // axios baseURL 在生产构建下为空串，须走 shared 的全路径约定
  // query 参数名跟随后端 FastAPI 签名（snake_case）
  const { data } = await apiClient.get<SessionListResponse>(
    `${API_BASE}/assistant/sessions`,
    {
      params: {
        limit: params?.limit,
        offset: params?.offset,
        agent_type: params?.agentType,
      },
    },
  )
  return data
}

export const createThread = async (data?: {
  agent_type?: AssistantAgentType
  title?: string
}): Promise<ThreadResponse> => {
  const { data: thread } = await apiClient.post<ThreadResponse>(
    `${API_BASE}/assistant/threads`,
    data ?? {},
  )
  return thread
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
