import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { ApiTopicsResponse } from '@ai-invest/shared'

vi.mock('@/hooks/useNewsTopics', () => ({
  useNewsTopics: vi.fn(),
}))

import { useNewsTopics } from '@/hooks/useNewsTopics'

import { TopicView } from './TopicView'

const mockTopics = vi.mocked(useNewsTopics)

function topicsPayload(
  overrides: Partial<ApiTopicsResponse> = {},
): ApiTopicsResponse {
  return {
    tradeDate: '2026-09-08',
    session: 'post',
    topics: [
      {
        title: '存储芯片涨价',
        sentiment: '利好',
        votes: { bullish: 5, bearish: 0, neutral: 1 },
        newsCount: 6,
        channelCounts: { cls_telegraph: 6 },
        heat: 70,
        factors: {
          newsCount: 6,
          sectorChangePct: 5,
          fundFlowNet: 5e8,
          asOfTradeDate: '2026-09-07',
        },
        sectors: [{ name: '半导体', changePct: 5, fundFlow: 5e8 }],
        chain: [
          { event: '海外大厂减产', link: '供给收缩', stocks: ['688012'] },
        ],
        itemIds: ['1', '2', '3'],
      },
    ],
    wordcloud: [
      { word: '存储', count: 9 },
      { word: '芯片', count: 5 },
    ],
    generatedAt: '2026-09-08T08:35:00Z',
    ...overrides,
  }
}

describe('TopicView', () => {
  it('renders topic cards with heat, votes and sectors', () => {
    mockTopics.mockReturnValue({
      data: topicsPayload(),
      isLoading: false,
    } as ReturnType<typeof useNewsTopics>)

    render(
      <MemoryRouter>
        <TopicView />
      </MemoryRouter>,
    )

    expect(screen.getByText('存储芯片涨价')).toBeInTheDocument()
    expect(screen.getByText('利好')).toBeInTheDocument()
    expect(screen.getByText('半导体')).toBeInTheDocument()
    expect(screen.getByText(/6 条资讯/)).toBeInTheDocument()
    expect(screen.getByText('70')).toBeInTheDocument() // 热度
  })

  it('marks T-1 sector factors for stale snapshots', () => {
    mockTopics.mockReturnValue({
      data: topicsPayload(),
      isLoading: false,
    } as ReturnType<typeof useNewsTopics>)

    render(
      <MemoryRouter>
        <TopicView />
      </MemoryRouter>,
    )

    expect(screen.getByText(/板块口径 2026-09-07（T-1 收盘）/)).toBeInTheDocument()
  })

  it('omits T-1 marker when no sector data', () => {
    mockTopics.mockReturnValue({
      data: topicsPayload({
        topics: [
          {
            title: '无板块主题',
            sentiment: '分歧',
            votes: { bullish: 1, bearish: 1, neutral: 1 },
            newsCount: 3,
            channelCounts: { cls_telegraph: 3 },
            heat: 20,
            factors: {
              newsCount: 3,
              sectorChangePct: null,
              fundFlowNet: null,
              asOfTradeDate: null,
            },
            sectors: [],
            chain: [],
            itemIds: ['1', '2', '3'],
          },
        ],
      }),
      isLoading: false,
    } as ReturnType<typeof useNewsTopics>)

    render(
      <MemoryRouter>
        <TopicView />
      </MemoryRouter>,
    )

    expect(screen.queryByText(/T-1 收盘/)).not.toBeInTheDocument()
    expect(screen.getAllByText(/主力净流入/).length).toBeGreaterThan(1)
  })

  it('switches session and passes it to query hook', () => {
    mockTopics.mockReturnValue({
      data: topicsPayload(),
      isLoading: false,
    } as ReturnType<typeof useNewsTopics>)

    render(
      <MemoryRouter>
        <TopicView />
      </MemoryRouter>,
    )
    expect(mockTopics).toHaveBeenCalledWith('post')

    fireEvent.click(screen.getByText('盘中 11:35'))
    expect(mockTopics).toHaveBeenCalledWith('intraday')
  })

  it('expands transmission chain on demand', () => {
    mockTopics.mockReturnValue({
      data: topicsPayload(),
      isLoading: false,
    } as ReturnType<typeof useNewsTopics>)

    render(
      <MemoryRouter>
        <TopicView />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('button', { name: /传导链/ }))
    expect(screen.getByText(/海外大厂减产/)).toBeInTheDocument()
    expect(screen.getByText('688012')).toBeInTheDocument()
  })
})
