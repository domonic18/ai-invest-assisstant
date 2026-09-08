import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import type { TelegraphItem } from '@ai-invest/shared'

import { TelegraphCard } from './TelegraphCard'

function item(overrides: Partial<TelegraphItem> = {}): TelegraphItem {
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
    sourceUrl: '',
    aiScore: null,
    aiFactors: null,
    subscribed: false,
    ...overrides,
  }
}

function renderCard(items: TelegraphItem[]) {
  return render(
    <MemoryRouter>
      <TelegraphCard items={items} />
    </MemoryRouter>,
  )
}

describe('TelegraphCard', () => {
  it('hides noise importance and numeric category tags', () => {
    renderCard([
      item({ clsMsgId: 1, importance: 1, category: '-1' }),
      item({ clsMsgId: 2, importance: null, category: '20026' }),
    ])

    expect(screen.queryByText('一般')).not.toBeInTheDocument()
    expect(screen.queryByText('-1')).not.toBeInTheDocument()
    expect(screen.queryByText('20026')).not.toBeInTheDocument()
  })

  it('shows meaningful importance and category tags', () => {
    renderCard([item({ clsMsgId: 3, importance: 3, category: '重点' })])

    expect(screen.getByText('重要')).toBeInTheDocument()
    expect(screen.getByText('重点')).toBeInTheDocument()
  })
})
