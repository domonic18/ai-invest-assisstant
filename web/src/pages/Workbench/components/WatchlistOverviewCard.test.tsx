import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import type { WorkbenchWatchlistGroup } from '@ai-invest/shared'

import { WatchlistOverviewCard } from './WatchlistOverviewCard'

function group(overrides: Partial<WorkbenchWatchlistGroup>): WorkbenchWatchlistGroup {
  return {
    id: 1,
    name: '分组',
    isDefault: false,
    aiReviewEnabled: false,
    items: [],
    ...overrides,
  }
}

function stock(code: string, name: string) {
  return {
    code,
    name,
    price: 10,
    changePct: 1,
    amount: null,
    tags: [],
    updatedAt: null,
    trend: [],
    aiStatus: 'off' as const,
    aiSummary: null,
  }
}

const groups: WorkbenchWatchlistGroup[] = [
  group({ id: 1, name: '核心持仓', items: [stock('600519', '贵州茅台')] }),
  group({
    id: 2,
    name: '默认分组',
    isDefault: true,
    items: [stock('000001', '平安银行'), stock('601318', '中国平安')],
  }),
]

function renderCard(list: WorkbenchWatchlistGroup[]) {
  return render(
    <MemoryRouter>
      <WatchlistOverviewCard groups={list} />
    </MemoryRouter>,
  )
}

describe('WatchlistOverviewCard', () => {
  it('defaults to the default group instead of the first group', () => {
    renderCard(groups)

    expect(screen.getByText('平安银行')).toBeInTheDocument()
    expect(screen.getByText('中国平安')).toBeInTheDocument()
    expect(screen.queryByText('贵州茅台')).not.toBeInTheDocument()
  })

  it('switches group on pill click', () => {
    renderCard(groups)

    fireEvent.click(screen.getByRole('button', { name: /核心持仓/ }))

    expect(screen.getByText('贵州茅台')).toBeInTheDocument()
    expect(screen.queryByText('平安银行')).not.toBeInTheDocument()
  })
})
