import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { ReviewStatus } from '@ai-invest/shared'

import { useReviewStatus } from '@/hooks/useWorkbench'

import { SidebarReviewStatus } from './SidebarReviewStatus'

vi.mock('@/hooks/useWorkbench', () => ({
  useReviewStatus: vi.fn(),
}))

const doneStatus: ReviewStatus = {
  status: 'done',
  tradeDate: '2026-09-08',
  generatedAt: '2026-09-08T08:32:00Z',
  durationSeconds: 134,
  plannedTime: '16:30',
  nextRunAt: '2026-09-09T08:30:00Z',
  streakDays: 3,
  monthSuccessRate: 96.4,
  recentDays: [
    { tradeDate: '2026-09-08', status: 'success' },
    { tradeDate: '2026-09-07', status: 'success' },
    { tradeDate: '2026-09-04', status: 'failed' },
  ],
}

function mockStatus(data: ReviewStatus | undefined) {
  vi.mocked(useReviewStatus).mockReturnValue({
    data,
  } as ReturnType<typeof useReviewStatus>)
}

describe('SidebarReviewStatus', () => {
  it('renders status title, review link and recent day dots', () => {
    mockStatus(doneStatus)
    render(
      <MemoryRouter>
        <SidebarReviewStatus />
      </MemoryRouter>,
    )

    expect(screen.getByText('今日复盘已生成')).toBeInTheDocument()
    expect(screen.getByText(/AI · \d{2}:\d{2} 生成/)).toBeInTheDocument()
    expect(screen.getByText('进入复盘 →').closest('a')).toHaveAttribute('href', '/review')
    expect(screen.getAllByTitle(/2026-09/)).toHaveLength(3)
  })

  it('renders nothing without data', () => {
    mockStatus(undefined)
    const { container } = render(
      <MemoryRouter>
        <SidebarReviewStatus />
      </MemoryRouter>,
    )

    expect(container).toBeEmptyDOMElement()
  })
})
