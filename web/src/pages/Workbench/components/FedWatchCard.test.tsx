import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { FedWatchResponse } from '@ai-invest/shared'

import { useFedWatch } from '@/hooks/useMarket'

import { FedWatchCard } from './FedWatchCard'

vi.mock('@/hooks/useMarket', () => ({
  useFedWatch: vi.fn(),
}))

const fedWatch: FedWatchResponse = {
  asOf: '2026-09-08',
  dataAsAt: '2026-09-08T06:30:00Z',
  currentRangeLow: 425,
  currentRangeHigh: 450,
  meetings: [
    {
      meetingDate: '2026-09-16',
      probHike: 2.1,
      probHold: 20.3,
      probCut: 77.6,
      likelyRangeLow: 400,
      likelyRangeHigh: 425,
    },
  ],
}

function mockUseFedWatch(data: FedWatchResponse | null, isLoading = false) {
  vi.mocked(useFedWatch).mockReturnValue({ data, isLoading } as ReturnType<typeof useFedWatch>)
}

describe('FedWatchCard', () => {
  it('renders next meeting probability rows and range', () => {
    mockUseFedWatch(fedWatch)
    render(
      <MemoryRouter>
        <FedWatchCard />
      </MemoryRouter>,
    )

    expect(screen.getByText('加息概率')).toBeInTheDocument()
    expect(screen.getByText('77.6%')).toBeInTheDocument()
    expect(screen.getByText('20.3%')).toBeInTheDocument()
    expect(screen.getByText('2.1%')).toBeInTheDocument()
    expect(screen.getByText(/4\.00-4\.25%/)).toBeInTheDocument()
  })

  it('shows empty state when no data', () => {
    mockUseFedWatch(null)
    render(
      <MemoryRouter>
        <FedWatchCard />
      </MemoryRouter>,
    )

    expect(screen.getByText(/暂无 FedWatch 数据/)).toBeInTheDocument()
  })
})
