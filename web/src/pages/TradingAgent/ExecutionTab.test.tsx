/** ExecutionTab 组件测试：summary 统计条、行卡片字段、显著/全部切换、空态文案。 */
import { fireEvent, render, screen } from '@testing-library/react'
import dayjs from 'dayjs'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { ApiTradingAgentObservationItem, ApiTradingAgentObservationPage } from '@ai-invest/shared'

vi.mock('@/hooks/useTradingAgent', () => ({
  useTradingAgentObservations: vi.fn(),
}))
vi.mock('./agentKeyContext', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./agentKeyContext')>()),
  useAgentKey: () => 'short-line',
}))

import { useTradingAgentObservations } from '@/hooks/useTradingAgent'

import { ExecutionTab } from './ExecutionTab'

const mockObservations = vi.mocked(useTradingAgentObservations)

const TICK_TIME = '2026-09-29T01:30:00Z'

function item(overrides: Partial<ApiTradingAgentObservationItem> = {}): ApiTradingAgentObservationItem {
  return {
    id: 1,
    tickTime: TICK_TIME,
    tradeDate: '2026-09-29',
    agentKey: 'short-line',
    planId: 11,
    stockCode: '600000',
    stockName: '浦发银行',
    planType: 'buy',
    price: 10.0,
    changePct: 1.01,
    l0Verdict: 'triggered',
    triggerReason: 'buy_zone',
    l0Detail: null,
    decision: {
      servedModel: 'openjev-0.1',
      choice: '立即执行',
      confidence: 0.52,
      noul: true,
      score: 3,
      window: null,
    },
    action: 'suppress',
    suppressionReason: 'below_threshold',
    isShadow: true,
    clOrdId: null,
    orderVolume: null,
    ...overrides,
  }
}

function page(overrides: Partial<ApiTradingAgentObservationPage> = {}): ApiTradingAgentObservationPage {
  return {
    tradeDate: '2026-09-29',
    total: 1,
    page: 1,
    pageSize: 20,
    items: [item()],
    summary: {
      totalTicks: 7,
      significantTicks: 1,
      l0VerdictCounts: { triggered: 1, no_action: 6 },
      actionCounts: { suppress: 1 },
      suppressionCounts: { below_threshold: 1 },
    },
    ...overrides,
  }
}

function setup(data: ApiTradingAgentObservationPage | undefined) {
  mockObservations.mockReturnValue({ data, isLoading: false } as unknown as ReturnType<
    typeof useTradingAgentObservations
  >)
  // 行卡片 useNavigate 跳个股详情，须有 Router 上下文
  return render(
    <MemoryRouter>
      <ExecutionTab />
    </MemoryRouter>,
  )
}

describe('ExecutionTab', () => {
  it('renders summary chips and row fields', () => {
    setup(page())

    expect(screen.getByText('2026-09-29 执行动态')).toBeInTheDocument()
    expect(screen.getByText('tick 7')).toBeInTheDocument()
    expect(screen.getByText('显著 1')).toBeInTheDocument()
    expect(screen.getByText('已触发 1')).toBeInTheDocument()
    expect(screen.getByText('低于阈值 1')).toBeInTheDocument()

    expect(screen.getByText('浦发银行')).toBeInTheDocument()
    expect(screen.getByText('600000')).toBeInTheDocument()
    expect(screen.getByText(dayjs(TICK_TIME).format('HH:mm:ss'))).toBeInTheDocument()
    expect(screen.getByText('抑制')).toBeInTheDocument()
    expect(screen.getByText('影子')).toBeInTheDocument()
    expect(screen.getByText('进入买点区间，置信不足未执行')).toBeInTheDocument()
    expect(screen.getByText('依据')).toBeInTheDocument()
    expect(screen.getByText('置信 52%（低）')).toBeInTheDocument()
    expect(screen.getByText('盘面 3.0/5 · 中性')).toBeInTheDocument()
    expect(screen.getByText('分时：支持买入')).toBeInTheDocument()
    expect(screen.getByText('openjev-0.1')).toBeInTheDocument()
  })

  it('renders heartbeat conclusion without evidence line in all view', () => {
    setup(
      page({
        items: [
          item({
            l0Verdict: 'no_action',
            triggerReason: null,
            l0Detail: '未触达止盈/止损价',
            decision: { servedModel: 'openjev-0.1', choice: null, confidence: null, noul: null, score: null, window: null },
            action: null,
            suppressionReason: null,
          }),
        ],
      }),
    )

    expect(screen.getByText('巡检正常 · 未触达止盈/止损价')).toBeInTheDocument()
    expect(screen.queryByText('依据')).not.toBeInTheDocument()
    expect(screen.queryByText('openjev-0.1')).not.toBeInTheDocument()
  })

  it('hides tail-check stock link and marks the row', () => {
    setup(
      page({
        items: [
          item({
            planId: null,
            planType: null,
            stockName: null,
            decision: { servedModel: null, choice: null, confidence: null, noul: null, score: null, window: 'tail_check' },
            l0Verdict: 'triggered',
            triggerReason: 'stop_loss',
          }),
        ],
      }),
    )

    expect(screen.getByText('尾盘强检')).toBeInTheDocument()
    expect(screen.queryByText('浦发银行')).not.toBeInTheDocument()
    expect(screen.getByText('600000')).toBeInTheDocument()
    expect(screen.getByText('尾盘强检：跌破止损，仅记录')).toBeInTheDocument()
  })

  it('switching to all resets to unfiltered query', () => {
    setup(page())

    fireEvent.click(screen.getByText('全部'))
    expect(mockObservations.mock.lastCall?.[1]?.significant).toBe(false)
  })

  it('shows significant-empty hint when no rows', () => {
    setup(
      page({
        items: [],
        total: 0,
        summary: {
          totalTicks: 0,
          significantTicks: 0,
          l0VerdictCounts: {},
          actionCounts: {},
          suppressionCounts: {},
        },
      }),
    )

    expect(screen.getByText(/该日无显著事件/)).toBeInTheDocument()
  })
})
