import { describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'

import { useAssistantSessions } from './useAssistantSessions'
import { fetchSessions, deleteSession } from '@/api/assistant'

vi.mock('@/api/assistant', () => ({
  fetchSessions: vi.fn(),
  deleteSession: vi.fn(),
}))

function wrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>
  }
}

describe('useAssistantSessions', () => {
  it('returns sessions from fetchSessions', async () => {
    const mockedFetch = vi.mocked(fetchSessions)
    mockedFetch.mockResolvedValueOnce({
      sessions: [
        {
          thread_id: 't-1',
          title: '测试',
          last_message_at: null,
          created_at: '2026-08-25T10:00:00Z',
          updated_at: '2026-08-25T10:00:00Z',
        },
      ],
      total: 1,
    })

    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { result } = renderHook(() => useAssistantSessions(), {
      wrapper: wrapper(client),
    })

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.sessions).toHaveLength(1)
    expect(result.current.sessions[0].title).toBe('测试')
  })

  it('calls deleteSession and invalidates cache', async () => {
    const mockedFetch = vi.mocked(fetchSessions)
    mockedFetch.mockResolvedValue({ sessions: [], total: 0 })
    const mockedDelete = vi.mocked(deleteSession)
    mockedDelete.mockResolvedValueOnce(undefined)

    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { result } = renderHook(() => useAssistantSessions(), {
      wrapper: wrapper(client),
    })

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    await result.current.deleteSessionById('t-1')

    expect(mockedDelete).toHaveBeenCalledWith('t-1')
    expect(client.isFetching({ queryKey: ['assistant-sessions'] })).toBeGreaterThan(0)
  })
})
