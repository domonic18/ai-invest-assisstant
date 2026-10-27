import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useReviewStatus } from '@/hooks/useWorkbench'

import { Layout } from './Layout'

vi.mock('@/hooks/useWorkbench', () => ({
  useReviewStatus: vi.fn(),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: (selector?: (s: Record<string, unknown>) => unknown) => {
    const state = { user: null, isAdmin: false, logout: vi.fn() }
    return selector ? selector(state) : state
  },
}))

describe('Layout', () => {
  beforeEach(() => {
    vi.mocked(useReviewStatus).mockReturnValue({} as ReturnType<typeof useReviewStatus>)
    // jsdom 未实现 requestIdleCallback（useIdlePrefetch 依赖）
    if (!window.requestIdleCallback) {
      window.requestIdleCallback = ((cb: IdleRequestCallback) => {
        const id = setTimeout(() => cb({ didTimeout: false, timeRemaining: () => 50 }), 0)
        return Number(id)
      }) as typeof window.requestIdleCallback
      window.cancelIdleCallback = ((id: number) => clearTimeout(id)) as typeof window.cancelIdleCallback
    }
  })

  it('renders app shell with sticky header inside a data router', () => {
    // <ScrollRestoration/> 仅在 data router 上下文合法（普通 MemoryRouter 会抛错），
    // 用 createMemoryRouter 渲染成功即证明接线正确
    const router = createMemoryRouter([{ path: '/', element: <Layout /> }])
    const { container } = render(
      <QueryClientProvider client={new QueryClient()}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    )

    expect(screen.getByRole('banner')).toHaveClass('sticky', 'top-0', 'z-30')
    expect(container.querySelector('main')).not.toBeNull()
    expect(container.querySelector('main')).not.toHaveClass('overflow-auto')
  })
})
