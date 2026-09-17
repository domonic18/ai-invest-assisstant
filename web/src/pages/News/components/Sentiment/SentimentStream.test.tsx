/** SentimentStream：跨日分组、筛选联动、转写降级角标、账号时间线切换。 */

import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'

import type { ApiSocialFeedItem, ApiSocialTimelineItem } from '@ai-invest/shared'

vi.mock('@/hooks/useSocialSentiment', () => ({
  useSentimentFeed: vi.fn(),
  useSocialAccountCards: vi.fn(),
  useSocialTimeline: vi.fn(),
  SENTIMENT_REFETCH_INTERVAL: 60_000,
}))

import { useSentimentFeed, useSocialTimeline } from '@/hooks/useSocialSentiment'

import { SentimentStream } from './SentimentStream'

const mockFeed = vi.mocked(useSentimentFeed)
const mockTimeline = vi.mocked(useSocialTimeline)

function feedItem(overrides: Partial<ApiSocialFeedItem>): ApiSocialFeedItem {
  return {
    postId: 1,
    videoId: 'v1',
    platform: 'douyin',
    accountId: 1,
    accountAlias: '财经大V',
    category: 'finance_kol',
    title: '今日复盘',
    caption: null,
    topicTags: [],
    coverUrl: null,
    durationSeconds: 120,
    publishedAt: '2026-09-15T02:00:00Z',
    diggCount: 10,
    commentCount: 5,
    shareCount: 1,
    transcriptMissing: false,
    isRelevant: true,
    stance: 'bearish',
    confidence: 0.9,
    coreArguments: ['量能萎缩，反弹动能不足'],
    targets: [{ targetType: 'index', name: '上证指数', code: '000001' }],
    summary: '短线承压，控制仓位',
    ...overrides,
  }
}

function feedResult(items: ApiSocialFeedItem[]) {
  return {
    data: { items, total: items.length, page: 1, pageSize: 30 },
    isLoading: false,
    isFetching: false,
    refetch: vi.fn(),
    dataUpdatedAt: Date.now(),
  } as unknown as ReturnType<typeof useSentimentFeed>
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('SentimentStream', () => {
  it('renders feed items grouped across days with separator', () => {
    mockFeed.mockReturnValue(
      feedResult([
        feedItem({ postId: 2, publishedAt: '2026-09-14T02:00:00Z' }),
        feedItem({ postId: 1, publishedAt: '2026-09-15T02:00:00Z' }),
      ]),
    )
    render(<SentimentStream account={null} onClearAccount={() => undefined} />)
    expect(screen.getAllByText('财经大V').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/短线承压，控制仓位/).length).toBeGreaterThan(0)
    expect(screen.getByText(/以下为 .* 资讯/)).toBeTruthy()
  })

  it('shows transcript missing badge for degraded items', () => {
    mockFeed.mockReturnValue(feedResult([feedItem({ transcriptMissing: true })]))
    render(<SentimentStream account={null} onClearAccount={() => undefined} />)
    expect(screen.getByText('未转写')).toBeTruthy()
  })

  it('passes stance and strongOnly filters to the feed query', () => {
    mockFeed.mockReturnValue(feedResult([]))
    render(<SentimentStream account={null} onClearAccount={() => undefined} />)
    fireEvent.click(screen.getByText('看空'))
    const lastCall = mockFeed.mock.calls[mockFeed.mock.calls.length - 1]
    expect(lastCall?.[2]).toMatchObject({ stance: 'bearish' })
  })

  it('switches to account timeline with back button', () => {
    const timelineItem: ApiSocialTimelineItem = {
      postId: 11,
      videoId: 'v11',
      title: '早盘提示',
      publishedAt: '2026-09-15T01:30:00Z',
      stance: 'bullish',
      confidence: 0.85,
      summary: '看多反弹',
      transcriptMissing: false,
    }
    mockFeed.mockReturnValue(feedResult([]))
    mockTimeline.mockReturnValue({
      data: { items: [timelineItem], total: 1, page: 1, pageSize: 30 },
      isLoading: false,
      isFetching: false,
      refetch: vi.fn(),
      dataUpdatedAt: Date.now(),
    } as unknown as ReturnType<typeof useSocialTimeline>)
    render(
      <SentimentStream
        account={{
          id: 7,
          alias: '财经大V',
          category: 'finance_kol',
          lastPostAt: null,
          latestStance: 'bullish',
          latestConfidence: 0.85,
          latestSummary: null,
          latestCoverUrl: null,
          bullishCount7d: 3,
          bearishCount7d: 1,
          neutralCount7d: 0,
        }}
        onClearAccount={() => undefined}
      />,
    )
    expect(mockTimeline).toHaveBeenCalled()
    expect(screen.getByText(/财经大V 的时间线/)).toBeTruthy()
    expect(screen.getByText('看多反弹')).toBeTruthy()
    fireEvent.click(screen.getByText('返回情绪流'))
  })
})
