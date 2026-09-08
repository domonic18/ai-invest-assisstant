import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { ApiFocusResponse } from '@ai-invest/shared'

vi.mock('@/hooks/useNewsFocus', () => ({
  useNewsFocus: vi.fn(),
  useStopNewsStory: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
    variables: undefined,
  })),
}))

import { useNewsFocus } from '@/hooks/useNewsFocus'

import { FocusView } from './FocusView'

const mockFocus = vi.mocked(useNewsFocus)

function focusPayload(
  overrides: Partial<ApiFocusResponse> = {},
): ApiFocusResponse {
  return {
    highlights: [
      {
        source: 'cls_telegraph',
        itemId: '1',
        title: '央行降准',
        content: '降准落地',
        publishTime: '2026-09-08T03:00:00Z',
        score: 85,
        factors: { impactScope: 90, certainty: 80, relatedCount: 30 },
        reason: '重磅',
      },
    ],
    storylines: [
      {
        id: 12,
        title: '降准故事线',
        summary: '摘要',
        status: 'tracking',
        origin: 'ai',
        reportCount: 6,
        firstSeenAt: '2026-09-07T01:00:00Z',
        lastSeenAt: '2026-09-08T03:00:00Z',
        latestBrief: '官宣降准',
        nodes: [{ time: '2026-09-08T03:00:00Z', brief: '官宣降准' }],
        userAction: null,
      },
    ],
    ...overrides,
  }
}

describe('FocusView', () => {
  it('renders factors three-band bars for scored highlights', () => {
    mockFocus.mockReturnValue({
      data: focusPayload(),
      isLoading: false,
    } as ReturnType<typeof useNewsFocus>)

    render(<FocusView />)

    expect(screen.getByText('影响范围')).toBeInTheDocument()
    expect(screen.getByText('确定性')).toBeInTheDocument()
    expect(screen.getByText('关联标的')).toBeInTheDocument()
    expect(screen.getByText('90')).toBeInTheDocument()
    expect(screen.getByText(/评分理由：重磅/)).toBeInTheDocument()
  })

  it('renders dash for legacy scores without factors', () => {
    mockFocus.mockReturnValue({
      data: focusPayload({
        highlights: [
          {
            source: 'cls_telegraph',
            itemId: '2',
            title: '旧评分',
            content: null,
            publishTime: '2026-09-08T02:00:00Z',
            score: 72,
            factors: null,
            reason: null,
          },
        ],
      }),
      isLoading: false,
    } as ReturnType<typeof useNewsFocus>)

    render(<FocusView />)

    expect(screen.getByText('构成 —')).toBeInTheDocument()
    // 无 factors 维度条与理由行
    expect(screen.queryByText('影响范围')).not.toBeInTheDocument()
    expect(screen.queryByText(/评分理由/)).not.toBeInTheDocument()
  })

  it('renders storyline cards with status/origin and stop action', () => {
    mockFocus.mockReturnValue({
      data: focusPayload(),
      isLoading: false,
    } as ReturnType<typeof useNewsFocus>)

    render(<FocusView />)

    expect(screen.getByText('跟踪中')).toBeInTheDocument()
    expect(screen.getByText('AI 自动建线')).toBeInTheDocument()
    expect(screen.getByText(/6 篇报道/)).toBeInTheDocument()
    expect(screen.getByText('最新进展：')).toBeInTheDocument()
    expect(screen.getByText('官宣降准')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /停止跟踪/ }).length).toBe(1)
  })

  it('marks manual storylines as hand-tracked', () => {
    mockFocus.mockReturnValue({
      data: focusPayload({
        storylines: [
          {
            id: 15,
            title: '手动线',
            summary: null,
            status: 'near_end',
            origin: 'manual',
            reportCount: 1,
            firstSeenAt: '2026-09-08T01:00:00Z',
            lastSeenAt: '2026-09-08T01:00:00Z',
            latestBrief: null,
            nodes: [],
            userAction: 'active',
          },
        ],
      }),
      isLoading: false,
    } as ReturnType<typeof useNewsFocus>)

    render(<FocusView />)

    expect(screen.getByText('手动跟踪')).toBeInTheDocument()
    expect(screen.getByText('临近尾声')).toBeInTheDocument()
  })

  it('shows empty state when nothing to display', () => {
    mockFocus.mockReturnValue({
      data: { highlights: [], storylines: [] },
      isLoading: false,
    } as unknown as ReturnType<typeof useNewsFocus>)

    render(<FocusView />)

    expect(screen.getByText(/暂无重点资讯/)).toBeInTheDocument()
  })
})
