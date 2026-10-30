/** ReviewCompareModal 测试：窗口 A/B 默认值、对比请求参数、对齐结果与空值渲染。 */
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type {
  ApiTradingAgentReviewCompareResponse,
  ApiTradingAgentReviewMetrics,
} from '@ai-invest/shared'

vi.mock('@/hooks/useTradingAgent', () => ({
  useCompareTradingAgentReviews: vi.fn(),
}))

import { useCompareTradingAgentReviews } from '@/hooks/useTradingAgent'

import { ReviewCompareModal } from './ReviewCompareModal'

const mockCompare = vi.mocked(useCompareTradingAgentReviews)

function metrics(overrides: Partial<ApiTradingAgentReviewMetrics> = {}): ApiTradingAgentReviewMetrics {
  return {
    period: 'month',
    startDate: '2026-09-01',
    endDate: '2026-09-30',
    tradingDays: 20,
    coveredStart: null,
    coveredEnd: null,
    startValue: null,
    endValue: null,
    returnPct: 8.5,
    annualizedReturnPct: null,
    maxDrawdownPct: 3.2,
    sellCount: 10,
    winRatePct: 60,
    profitLossRatio: 1.8,
    turnoverRatePct: 120,
    executionDeviationPct: -1.5,
    benchmarkReturnPct: 2.1,
    excessReturnPct: 6.4,
    notes: [],
    ...overrides,
  }
}

function setup(
  result: ApiTradingAgentReviewCompareResponse | null = null,
): { mutate: ReturnType<typeof vi.fn>; unmount: () => void } {
  const mutate = vi.fn((_payload, options?: { onSuccess?: (data: ApiTradingAgentReviewCompareResponse) => void }) => {
    if (result && options?.onSuccess) options.onSuccess(result)
  })
  mockCompare.mockReturnValue({ mutate, isPending: false } as unknown as ReturnType<
    typeof useCompareTradingAgentReviews
  >)
  const { unmount } = render(
    <ReviewCompareModal
      open
      onClose={vi.fn()}
      agentKey="short-line"
      baseWindow={{ period: 'month', scope: 'current' }}
    />,
  )
  return { mutate, unmount }
}

describe('ReviewCompareModal', () => {
  it('展示窗口 A 描述，窗口 B 默认同周期上期', () => {
    setup()

    expect(screen.getByText(/窗口 A：月本期（面板当前窗口）/)).toBeInTheDocument()
    expect(screen.getByText(/选择窗口 B 后点击「对比」；两个窗口都须已生成复盘/)).toBeInTheDocument()
  })

  it('点击对比时窗口 A 沿用面板窗口，B 默认上期', () => {
    const { mutate } = setup()

    fireEvent.click(screen.getByRole('button', { name: /对\s*比/ }))

    expect(mutate).toHaveBeenCalledWith(
      {
        windowA: { period: 'month', scope: 'current' },
        windowB: { period: 'month', scope: 'previous', tradeDate: undefined },
      },
      expect.anything(),
    )
  })

  it('对比结果渲染对齐交易日数与指标行，空值显示 -', () => {
    setup({
      windowA: metrics(),
      windowB: metrics({ returnPct: null, excessReturnPct: null }),
      alignedTradingDays: 20,
      note: '两侧窗口交易日数一致',
    })

    fireEvent.click(screen.getByRole('button', { name: /对\s*比/ }))

    expect(screen.getByText('按 20 个交易日对齐')).toBeInTheDocument()
    expect(screen.getByText('两侧窗口交易日数一致')).toBeInTheDocument()
    expect(screen.getByText('区间收益')).toBeInTheDocument()
    expect(screen.getByText('超额收益')).toBeInTheDocument()
    // A 侧两个数值 + B 侧两处空值占位
    expect(screen.getAllByText('-').length).toBeGreaterThanOrEqual(2)
  })

  it('对比后修改窗口 B，表头仍对应已对比的窗口（不随草稿漂移）', () => {
    setup({
      windowA: metrics(),
      windowB: metrics(),
      alignedTradingDays: 20,
      note: '两侧窗口交易日数一致',
    })

    fireEvent.click(screen.getByRole('button', { name: /对\s*比/ }))
    expect(screen.getByText('B · 月上期')).toBeInTheDocument()

    fireEvent.mouseDown(screen.getAllByRole('combobox')[0])
    fireEvent.click(screen.getByTitle('季'))

    expect(screen.getByText('B · 月上期')).toBeInTheDocument()
    expect(screen.queryByText('B · 季上期')).not.toBeInTheDocument()
  })

  it('切换 B 周期为季、作用域为本期后按新窗口请求', () => {
    const { mutate } = setup()

    fireEvent.mouseDown(screen.getAllByRole('combobox')[0])
    fireEvent.click(screen.getByTitle('季'))
    fireEvent.mouseDown(screen.getAllByRole('combobox')[1])
    fireEvent.click(screen.getByTitle('本期'))
    fireEvent.click(screen.getByRole('button', { name: /对\s*比/ }))

    expect(mutate).toHaveBeenCalledWith(
      {
        windowA: { period: 'month', scope: 'current' },
        windowB: { period: 'quarter', scope: 'current', tradeDate: undefined },
      },
      expect.anything(),
    )
  })
})
