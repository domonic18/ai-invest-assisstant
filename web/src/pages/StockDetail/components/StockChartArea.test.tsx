/**
 * 切股视图继承契约：自选分组逐个查看股票时，单/双图与上/下图周期
 * 从会话 store 继承，不随股票切换重置（2026-11-11 用户反馈的回归防护）。
 */
import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useKlineViewLayoutStore } from '@/stores/klineViewLayout'

import { StockChartArea } from './StockChartArea'

const latest = new Map<string, { defaultPeriod?: string }>()

vi.mock('@/components/charts/stockChartView', () => ({
  CHROME_HEIGHT: 37,
  StockChartView: (props: {
    viewId: string
    defaultPeriod?: string
    onPeriodChange?: (period: string) => void
    layoutToggle?: { value: boolean; onChange: (dual: boolean) => void }
  }) => {
    latest.set(props.viewId, props)
    return (
      <div data-testid={`view-${props.viewId}`}>
        {props.layoutToggle && (
          <button
            data-testid={`toggle-${props.viewId}`}
            onClick={() => props.layoutToggle?.onChange(true)}
          >
            dual
          </button>
        )}
        <button
          data-testid={`period-${props.viewId}`}
          onClick={() => props.onPeriodChange?.('monthly')}
        >
          monthly
        </button>
      </div>
    )
  },
}))

vi.mock('@/hooks/usePaperTrade', () => ({
  usePaperTradeTradeMarkers: () => ({ data: undefined }),
}))

vi.mock('@/hooks/useIsNarrowScreen', () => ({
  useIsNarrowScreen: () => false,
}))

describe('StockChartArea 切股视图继承', () => {
  beforeEach(() => {
    useKlineViewLayoutStore.setState({ dual: false, periods: {}, windows: {} })
    localStorage.clear()
    latest.clear()
  })

  it('单/双图与各视图周期切股继承，不重置回单图', () => {
    const { rerender } = render(<StockChartArea stockCode="600519" />)
    expect(screen.queryByTestId('view-weekly')).not.toBeInTheDocument()

    fireEvent.click(screen.getByTestId('toggle-daily'))
    expect(screen.getByTestId('view-weekly')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('period-weekly'))
    expect(useKlineViewLayoutStore.getState().periods.weekly).toBe('monthly')

    rerender(<StockChartArea stockCode="000001" />)
    expect(useKlineViewLayoutStore.getState().dual).toBe(true)
    expect(screen.getByTestId('view-weekly')).toBeInTheDocument()
    expect(latest.get('weekly')?.defaultPeriod).toBe('monthly')
    expect(latest.get('daily')?.defaultPeriod).toBe('daily')
  })

  it('上/下视图周期各记各的：仅调上视图不影响下视图', () => {
    const { rerender } = render(<StockChartArea stockCode="600519" />)
    fireEvent.click(screen.getByTestId('toggle-daily'))
    fireEvent.click(screen.getByTestId('period-daily'))

    rerender(<StockChartArea stockCode="000001" />)
    expect(latest.get('daily')?.defaultPeriod).toBe('monthly')
    expect(latest.get('weekly')?.defaultPeriod).toBe('weekly')
  })

  it('会话未调整周期时回退各股持久化值', () => {
    localStorage.setItem(
      'ai-invest.stock-detail.views.v2.000001',
      JSON.stringify([{ id: 'daily', period: 'weekly', indicators: {} }]),
    )
    render(<StockChartArea stockCode="000001" />)
    expect(latest.get('daily')?.defaultPeriod).toBe('weekly')
  })

  it('切回曾看过的股票同样继承会话周期', () => {
    const { rerender } = render(<StockChartArea stockCode="600519" />)
    fireEvent.click(screen.getByTestId('period-daily'))
    rerender(<StockChartArea stockCode="000001" />)
    rerender(<StockChartArea stockCode="600519" />)
    expect(latest.get('daily')?.defaultPeriod).toBe('monthly')
  })
})
