import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { TelegraphPage } from '@ai-invest/shared'

vi.mock('@/hooks/useTelegraph', () => ({
  useTelegraph: vi.fn(),
}))
vi.mock('@/hooks/useNewsFocus', () => ({
  useCreateNewsStory: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
    variables: undefined,
  })),
}))

import { useTelegraph } from '@/hooks/useTelegraph'

import { NewsFeedView } from './NewsFeedView'

const mockTelegraph = vi.mocked(useTelegraph)

function page(items: TelegraphPage['items']): TelegraphPage {
  return { total: items.length, page: 1, pageSize: 30, items }
}

function item(overrides: Partial<TelegraphPage['items'][number]> = {}) {
  return {
    clsMsgId: 1,
    title: '快讯标题',
    content: '正文',
    category: null,
    importance: null,
    shared: null,
    stockCodes: [],
    publishTime: '2026-09-08T03:00:00Z',
    sourceUrl: 'https://example.com/1',
    aiScore: 85,
    aiFactors: null,
    subscribed: false,
    ...overrides,
  }
}

function setupHookResult(data: TelegraphPage) {
  mockTelegraph.mockReturnValue({
    data,
    isLoading: false,
    isFetching: false,
    refetch: vi.fn(),
    dataUpdatedAt: 0,
  } as unknown as ReturnType<typeof useTelegraph>)
}

describe('NewsFeedView', () => {
  it('marks subscription hits with star and offers manual storyline tracking', () => {
    setupHookResult(
      page([item({ clsMsgId: 1, subscribed: true }), item({ clsMsgId: 2 })]),
    )

    const { container } = render(<NewsFeedView channels={[]} />)

    // 订阅命中条目标 ★（antd Tooltip title 不落 DOM，以星形图标断言）
    expect(container.querySelectorAll('.anticon-star').length).toBe(1)
    expect(screen.getAllByRole('button', { name: /跟踪此事件/ }).length).toBe(2)
  })

  it('toggles subscription_only filter via chip', () => {
    setupHookResult(page([item()]))

    render(<NewsFeedView channels={[]} />)

    // 初始不开启订阅过滤
    expect(mockTelegraph.mock.calls[mockTelegraph.mock.calls.length - 1].slice(4)).toEqual([true, false])
    fireEvent.click(screen.getByText('★ 仅看订阅命中'))
    expect(mockTelegraph.mock.calls[mockTelegraph.mock.calls.length - 1].slice(4)).toEqual([true, true])
  })
})
