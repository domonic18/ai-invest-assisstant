import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { useGlobalIndices, useIndexKline } from '@/hooks/useMarket'

import { IndexDetail } from './IndexDetail'

vi.mock('@/hooks/useMarket', () => ({
  useIndexKline: vi.fn(),
  useGlobalIndices: vi.fn(),
}))

vi.mock('@/pages/Dashboard/components/IndexChartPanel', () => ({
  IndexChartPanel: ({ code, noIntraday }: { code: string; noIntraday?: boolean }) => (
    <div data-testid="kline-panel" data-code={code} data-no-intraday={String(noIntraday)} />
  ),
}))

vi.mock('./GlobalIndexKlinePanel', () => ({
  GlobalIndexKlinePanel: ({ code, decimals }: { code: string; decimals?: number }) => (
    <div data-testid="global-kline-panel" data-code={code} data-decimals={String(decimals ?? 2)} />
  ),
}))

function mockHooks(klineName: string | null, globalQuotes: { indexCode: string; indexName: string; close: number | null }[] = []) {
  vi.mocked(useIndexKline).mockReturnValue({
    data: klineName ? { code: 'x', name: klineName, period: 'daily', bars: [] } : undefined,
  } as unknown as ReturnType<typeof useIndexKline>)
  vi.mocked(useGlobalIndices).mockReturnValue({
    data: globalQuotes.map((q) => ({
      indexCode: q.indexCode,
      indexName: q.indexName,
      close: q.close,
      changePct: null,
      tradeDate: '2026-09-08',
      trend: [],
    })),
  } as unknown as ReturnType<typeof useGlobalIndices>)
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/index/:code" element={<IndexDetail />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('IndexDetail', () => {
  it('renders kline panel with intraday for tracked A-share index', () => {
    mockHooks('上证指数')
    renderAt('/index/sh000001')

    expect(screen.getByTestId('kline-panel')).toHaveAttribute('data-code', 'sh000001')
    expect(screen.getByTestId('kline-panel')).toHaveAttribute('data-no-intraday', 'false')
    expect(screen.getByText('上证指数')).toBeInTheDocument()
    expect(screen.queryByTestId('global-kline-panel')).not.toBeInTheDocument()
  })

  it('hides intraday for kline-extra codes without minute data', () => {
    mockHooks('富时A50')
    renderAt('/index/CN00Y')

    expect(screen.getByTestId('kline-panel')).toHaveAttribute('data-no-intraday', 'true')
  })

  it('renders global kline panel with bond decimals and snapshot header', () => {
    mockHooks(null, [{ indexCode: 'US10Y', indexName: '美债 10Y 收益率', close: 3.842 }])
    renderAt('/index/US10Y')

    const panel = screen.getByTestId('global-kline-panel')
    expect(panel).toHaveAttribute('data-code', 'US10Y')
    expect(panel).toHaveAttribute('data-decimals', '3')
    expect(screen.getByText('美债 10Y 收益率')).toBeInTheDocument()
    expect(screen.getByText('3.842%')).toBeInTheDocument()
    expect(screen.queryByTestId('kline-panel')).not.toBeInTheDocument()
  })
})
