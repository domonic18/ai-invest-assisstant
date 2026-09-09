import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
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
    stocks: [],
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

function renderFeed() {
  return render(
    <MemoryRouter>
      <NewsFeedView channels={[]} />
    </MemoryRouter>,
  )
}

describe('NewsFeedView', () => {
  it('marks subscription hits with star and offers manual storyline tracking', () => {
    setupHookResult(
      page([item({ clsMsgId: 1, subscribed: true }), item({ clsMsgId: 2 })]),
    )

    const { container } = renderFeed()

    // 订阅命中条目标 ★（antd Tooltip title 不落 DOM，以星形图标断言）
    expect(container.querySelectorAll('.anticon-star').length).toBe(1)
    expect(screen.getAllByRole('button', { name: /跟踪此事件/ }).length).toBe(2)
  })

  it('renders enriched stocks with name and change pct', () => {
    setupHookResult(
      page([
        item({
          clsMsgId: 3,
          stockCodes: ['sz300750'],
          stocks: [{ code: '300750', name: '宁德时代', changePct: 1.5 }],
        }),
        item({ clsMsgId: 4, stockCodes: ['sh600000'] }),
      ]),
    )

    renderFeed()

    // 富化命中：名称 + 涨跌幅，链接直达个股页
    expect(screen.getByText('宁德时代')).toBeInTheDocument()
    expect(screen.getByText('+1.50%')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /宁德时代/ })).toHaveAttribute(
      'href',
      '/stock/300750',
    )
    // 未富化回退原始代码
    expect(screen.getByText('sh600000')).toBeInTheDocument()
  })

  it('hides noise importance and numeric category tags', () => {
    setupHookResult(
      page([item({ clsMsgId: 5, importance: 1, category: '-1' })]),
    )

    renderFeed()

    expect(screen.queryByText('一般')).not.toBeInTheDocument()
    expect(screen.queryByText('-1')).not.toBeInTheDocument()
  })

  it('toggles subscription_only filter via chip', () => {
    setupHookResult(page([item()]))

    renderFeed()

    // 初始不开启订阅过滤
    expect(mockTelegraph.mock.calls[mockTelegraph.mock.calls.length - 1].slice(4)).toEqual([true, false])
    fireEvent.click(screen.getByText('★ 仅看订阅命中'))
    expect(mockTelegraph.mock.calls[mockTelegraph.mock.calls.length - 1].slice(4)).toEqual([true, true])
  })
})
