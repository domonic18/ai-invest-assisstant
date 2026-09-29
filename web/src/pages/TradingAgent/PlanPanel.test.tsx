/** PlanPanel 组件测试：制定→执行日期轴、空态执行计划引导跳转。 */
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { ApiTradingAgentPlan, ApiTradingAgentPlansResponse } from '@ai-invest/shared'

vi.mock('@/hooks/useTradingAgent', () => ({
  useTradingAgentPlans: vi.fn(),
  useTradingAgentDates: vi.fn(),
  useCancelTradingAgentPlan: vi.fn(() => ({ mutate: vi.fn() })),
}))
vi.mock('./agentKeyContext', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./agentKeyContext')>()),
  useAgentKey: () => 'short-line',
}))

import { useTradingAgentDates, useTradingAgentPlans } from '@/hooks/useTradingAgent'

import { PlanPanel } from './PlanPanel'

const mockPlans = vi.mocked(useTradingAgentPlans)
const mockDates = vi.mocked(useTradingAgentDates)

function plan(overrides: Partial<ApiTradingAgentPlan> = {}): ApiTradingAgentPlan {
  return {
    id: 1,
    planDate: '2026-09-28',
    planType: 'sell',
    stockCode: '600000',
    stockName: '浦发银行',
    strategy: '破位止损',
    buyZoneLow: null,
    buyZoneHigh: null,
    targetPrice: 11.5,
    stopLoss: 9.5,
    positionPct: 10,
    selectionId: null,
    basis: '跌破止损位离场',
    status: 'executed',
    heldVolume: 100,
    triggeredClOrdId: null,
    ...overrides,
  }
}

function data(overrides: Partial<ApiTradingAgentPlansResponse> = {}): ApiTradingAgentPlansResponse {
  return {
    tradeDate: '2026-09-28',
    nextTradeDate: '2026-09-29',
    plans: [plan()],
    standAsideReason: null,
    executingPlanDate: null,
    ...overrides,
  }
}

function setup(payload: ApiTradingAgentPlansResponse) {
  mockPlans.mockReturnValue({ data: payload, isLoading: false } as unknown as ReturnType<
    typeof useTradingAgentPlans
  >)
  mockDates.mockReturnValue({ data: { planDates: ['2026-09-28'] } } as unknown as ReturnType<
    typeof useTradingAgentDates
  >)
  // PlanRow useNavigate 跳个股详情，须有 Router 上下文
  return render(
    <MemoryRouter>
      <PlanPanel />
    </MemoryRouter>,
  )
}

describe('PlanPanel', () => {
  it('renders make→execute date axis with weekday labels', () => {
    setup(data())

    // 2026-09-28 周一 / 2026-09-29 周二
    expect(screen.getByText(/制定 2026-09-28（周一）→ 执行 2026-09-29（周二）盘中/)).toBeInTheDocument()
  })

  it('shows executing-plan hint on empty date for navigation', () => {
    setup(data({ plans: [], executingPlanDate: '2026-09-25' }))

    expect(screen.getByText(/该日盘中执行的是 2026-09-25 制定的计划/)).toBeInTheDocument()
  })

  it('omits hint when no executing plan date', () => {
    setup(data({ plans: [] }))

    expect(screen.getByText(/该日未生成计划/)).toBeInTheDocument()
    expect(screen.queryByText(/制定的计划 → 查看/)).not.toBeInTheDocument()
  })
})
