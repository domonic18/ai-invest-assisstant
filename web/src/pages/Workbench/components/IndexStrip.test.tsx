import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import type { GlobalIndexQuote, IndexQuote } from '@ai-invest/shared'

import { IndexStrip } from './IndexStrip'

const index: IndexQuote = {
  code: 'sh000001',
  name: '上证指数',
  price: 3250.5,
  change: 12.3,
  changePct: 0.38,
  amount: null,
  trend: [],
}

const globalQuote = (code: string, name: string): GlobalIndexQuote => ({
  indexCode: code,
  indexName: name,
  close: 100,
  changePct: -0.5,
  tradeDate: '2026-09-08',
  trend: [],
})

function renderStrip(indices: IndexQuote[], globalIndices: GlobalIndexQuote[]) {
  return render(
    <MemoryRouter>
      <IndexStrip indices={indices} globalIndices={globalIndices} />
    </MemoryRouter>,
  )
}

describe('IndexStrip', () => {
  it('shows A-share tab by default and hides other groups', () => {
    renderStrip([index], [globalQuote('US10Y', '美债 10Y 收益率'), globalQuote('GC00Y', 'COMEX 黄金')])

    expect(screen.getByText('上证指数')).toBeInTheDocument()
    expect(screen.queryByText('美债 10Y 收益率')).not.toBeInTheDocument()
    expect(screen.queryByText('COMEX 黄金')).not.toBeInTheDocument()
    expect(screen.getByText('A股')).toBeInTheDocument()
    expect(screen.getByText('债券')).toBeInTheDocument()
    expect(screen.getByText('商品')).toBeInTheDocument()
  })

  it('switches group on tab click', () => {
    renderStrip([index], [globalQuote('US10Y', '美债 10Y 收益率')])

    fireEvent.click(screen.getByText('债券'))

    expect(screen.getByText('美债 10Y 收益率')).toBeInTheDocument()
    expect(screen.queryByText('上证指数')).not.toBeInTheDocument()
  })

  it('tiles link to index detail page', () => {
    renderStrip([index], [])
    expect(screen.getByText('上证指数').closest('a')).toHaveAttribute('href', '/index/sh000001')
  })
})
