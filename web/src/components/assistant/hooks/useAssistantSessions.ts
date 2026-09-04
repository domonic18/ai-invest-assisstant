import { useQuery, useQueryClient } from '@tanstack/react-query'

import { deleteSession, fetchSessions, type AssistantSessionItem } from '@/api/assistant'

const QUERY_KEY = ['assistant-sessions']

interface UseAssistantSessionsReturn {
  sessions: AssistantSessionItem[]
  isLoading: boolean
  error: Error | null
  deleteSessionById: (threadId: string) => Promise<void>
  refresh: () => void
}

interface UseAssistantSessionsOptions {
  enabled?: boolean
}

/** 拉取当前用户会话列表，提供删除与刷新能力。 */
export function useAssistantSessions(
  options: UseAssistantSessionsOptions = {},
): UseAssistantSessionsReturn {
  const queryClient = useQueryClient()
  const { data, isLoading, error } = useQuery({
    queryKey: QUERY_KEY,
    queryFn: () => fetchSessions({ limit: 100 }),
    staleTime: 30 * 1000,
    enabled: options.enabled,
  })

  const deleteSessionById = async (threadId: string) => {
    await deleteSession(threadId)
    queryClient.invalidateQueries({ queryKey: QUERY_KEY })
  }

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: QUERY_KEY })
  }

  return {
    sessions: data?.sessions ?? [],
    isLoading,
    error,
    deleteSessionById,
    refresh,
  }
}
