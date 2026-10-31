/** ReviewPanel 组件测试：六档周期请求窗口、本期/上期切换、空态文案与对比入口。 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { ApiTradingAgentReview } from '@ai-invest/shared'

vi.mock('@/hooks/useTradingAgent', () => ({
  useTradingAgentReview: vi.fn(),
  useTradingAgentDates: vi.fn(),
  useGenerateTradingAgentReview: vi.fn(),
  useReviewGenerationStatus: vi.fn(),
  useCompareTradingAgentReviews: vi.fn(),
}))
vi.mock('./agentKeyContext', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./agentKeyContext')>()),
  useAgentKey: () => 'short-line',
}))

import {
  useCompareTradingAgentReviews,
  useGenerateTradingAgentReview,
  useReviewGenerationStatus,
  useTradingAgentDates,
  useTradingAgentReview,
} from '@/hooks/useTradingAgent'

import { ReviewPanel } from './ReviewPanel'

const mockReview = vi.mocked(useTradingAgentReview)
const mockDates = vi.mocked(useTradingAgentDates)
const mockGenerate = vi.mocked(useGenerateTradingAgentReview)
const mockGenerationStatus = vi.mocked(useReviewGenerationStatus)
const mockCompare = vi.mocked(useCompareTradingAgentReviews)

function review(overrides: Partial<ApiTradingAgentReview> = {}): ApiTradingAgentReview {
  return {
    period: 'day',
    tradeDate: '2026-10-30',
    overall: '震荡市，按计划轻仓试错',
    trades: [],
    bias: '无',
    suggestion: '维持纪律',
    sections: [],
    marketContext: '',
    methodologyCheck: [],
    experiences: [],
    noTargetReason: null,
    metrics: null,
    ...overrides,
  }
}

function setup(
  data: ApiTradingAgentReview | null,
  error: unknown = null,
) {
  mockReview.mockReturnValue({ data, isLoading: false, error, refetch: vi.fn() } as unknown as ReturnType<
    typeof useTradingAgentReview
  >)
  mockDates.mockReturnValue({ data: { planDates: [], reviewDates: {} } } as unknown as ReturnType<
    typeof useTradingAgentDates
  >)
  mockGenerate.mockReturnValue({ mutate: vi.fn(), isPending: false } as unknown as ReturnType<
    typeof useGenerateTradingAgentReview
  >)
  mockGenerationStatus.mockReturnValue({ data: undefined } as unknown as ReturnType<
    typeof useReviewGenerationStatus
  >)
  mockCompare.mockReturnValue({ mutate: vi.fn(), isPending: false } as unknown as ReturnType<
    typeof useCompareTradingAgentReviews
  >)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <ReviewPanel />
    </QueryClientProvider>,
  )
}

/** 最近一次渲染传给读取 hook 的窗口参数。 */
function lastWindow() {
  const calls = mockReview.mock.calls
  return calls[calls.length - 1]?.[1]
}

describe('ReviewPanel', () => {
  it('默认请求日档本期窗口', () => {
    setup(null)

    expect(lastWindow()).toEqual({ period: 'day', scope: 'current', tradeDate: undefined })
    expect(screen.getByText(/当前日复盘尚未生成/)).toBeInTheDocument()
  })

  it('切换到季档后按季度期请求，空态提示按需生成', () => {
    setup(null)

    fireEvent.click(screen.getByText('季'))

    expect(lastWindow()).toEqual({ period: 'quarter', scope: 'current', tradeDate: undefined })
    expect(screen.getByText('季档按需生成，点击「生成复盘」触发')).toBeInTheDocument()
  })

  it('切换到上期后窗口带 scope=previous', () => {
    setup(null)

    fireEvent.click(screen.getByText('上期'))

    expect(lastWindow()).toEqual({ period: 'day', scope: 'previous', tradeDate: undefined })
    expect(screen.getByText(/上一日复盘尚未生成/)).toBeInTheDocument()
  })

  it('404 走空态，其余错误展示真实故障与重试', () => {
    setup(null, { response: { status: 404 }, isAxiosError: true })
    expect(screen.getByText(/当前日复盘尚未生成/)).toBeInTheDocument()
    expect(screen.queryByText('复盘加载失败')).not.toBeInTheDocument()

    setup(null, {
      response: { status: 500, data: { detail: '内部错误' } },
      isAxiosError: true,
    })
    expect(screen.getByText('复盘加载失败')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /重\s*试/ })).toBeInTheDocument()
  })

  it('已执行但空仓时展示「无复盘对象」说明', () => {
    setup(review({ noTargetReason: '窗口内无交易且无持仓' }))

    expect(screen.getByText('已执行 · 无复盘对象')).toBeInTheDocument()
    expect(screen.getByText('窗口内无交易且无持仓')).toBeInTheDocument()
  })

  it('无复盘时对比按钮禁用，有复盘时可用', () => {
    const { unmount } = setup(null)
    expect(screen.getByRole('button', { name: /对\s*比/ })).toBeDisabled()
    unmount()

    setup(review())
    expect(screen.getByRole('button', { name: /对\s*比/ })).toBeEnabled()
  })

  it('点击生成时把当前窗口与 regenerate 标记传给 mutation', () => {
    const mutate = vi.fn()
    mockReview.mockReturnValue({ data: review(), isLoading: false } as unknown as ReturnType<
      typeof useTradingAgentReview
    >)
    mockGenerate.mockReturnValue({ mutate, isPending: false } as unknown as ReturnType<
      typeof useGenerateTradingAgentReview
    >)
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <ReviewPanel />
      </QueryClientProvider>,
    )

    fireEvent.click(screen.getByRole('button', { name: /重新生成/ }))

    expect(mutate).toHaveBeenCalledWith(
      { period: 'day', scope: 'current', tradeDate: undefined, regenerate: true },
      expect.anything(),
    )
  })
})
