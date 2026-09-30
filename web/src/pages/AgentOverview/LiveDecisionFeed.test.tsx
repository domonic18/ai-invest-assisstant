/** LiveDecisionFeed 组件测试：会话 badge 分态、行字段与心跳弱化、尾盘/影子标记、无 active agent 隐藏。 */
import { render, screen } from '@testing-library/react'
import dayjs from 'dayjs'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type {
  AgentOverviewItem,
  ApiTradingAgentObservationItem,
  ApiTradingAgentObservationPage,
  TradingAgentProfile,
} from '@ai-invest/shared'

vi.mock('@/hooks/useTradingAgent', () => ({
  useLiveAgentObservations: vi.fn(),
}))
vi.mock('@/pages/PaperTrade/tradingRules', () => ({
  marketSession: vi.fn(),
  isMarketOpen: vi.fn(),
}))

import { useLiveAgentObservations } from '@/hooks/useTradingAgent'
import { marketSession } from '@/pages/PaperTrade/tradingRules'

import { LiveDecisionFeed } from './LiveDecisionFeed'

const mockLive = vi.mocked(useLiveAgentObservations)
const mockSession = vi.mocked(marketSession)

const TICK_TIME = '2026-09-28T01:32:00Z'

function profile(overrides: Partial<TradingAgentProfile> = {}): TradingAgentProfile {
  return {
    agentKey: 'short-line',
    name: '短线 agent',
    tagline: '日内短线',
    llmConfigId: null,
    methodologySourceId: null,
    riskMaxPositionPct: 20,
    riskMaxTotalPct: 60,
    riskMaxDailyOrders: 6,
    intradayExecMode: 'shadow',
    intradayPaused: false,
    calibrationMode: 'shadow',
    status: 'active',
    planCadence: 'daily',
    reviewCadence: 'daily',
    sortOrder: 0,
    promptId: 'short-line',
    accentColor: '#38bdf8',
    updatedAt: null,
    ...overrides,
  }
}

function agentItem(overrides: Partial<AgentOverviewItem> = {}): AgentOverviewItem {
  return {
    profile: profile(),
    llmName: null,
    runtimeState: 'working',
    stateLabel: null,
    accountName: null,
    planCount: 2,
    selectionCount: 3,
    orderCount: 0,
    recentActivity: [],
    nextTasks: [],
    ...overrides,
  }
}

function item(overrides: Partial<ApiTradingAgentObservationItem> = {}): ApiTradingAgentObservationItem {
  return {
    id: 1,
    tickTime: TICK_TIME,
    tradeDate: '2026-09-28',
    agentKey: 'short-line',
    planId: 13,
    stockCode: '600000',
    stockName: '浦发银行',
    planType: 'sell',
    price: 10.05,
    changePct: 0.7,
    l0Verdict: 'no_action',
    triggerReason: null,
    l0Detail: null,
    decision: null,
    action: null,
    suppressionReason: null,
    isShadow: true,
    clOrdId: null,
    orderVolume: null,
    ...overrides,
  }
}

function page(overrides: Partial<ApiTradingAgentObservationPage> = {}): ApiTradingAgentObservationPage {
  return {
    tradeDate: '2026-09-28',
    total: 1,
    page: 1,
    pageSize: 25,
    items: [item()],
    summary: {
      totalTicks: 7,
      significantTicks: 1,
      l0VerdictCounts: { no_action: 6, triggered: 1 },
      actionCounts: { suppress: 1 },
      suppressionCounts: { below_threshold: 1 },
    },
    ...overrides,
  }
}

function setup({
  items = [agentItem()],
  isLoading = false,
  session = 'open',
  selectedKey,
  data,
}: {
  items?: AgentOverviewItem[]
  isLoading?: boolean
  session?: 'open' | 'break' | 'pre' | 'closed'
  selectedKey?: string | null
  data?: ApiTradingAgentObservationPage
}) {
  mockSession.mockReturnValue(session)
  mockLive.mockReturnValue({
    data,
    isLoading: false,
  } as unknown as ReturnType<typeof useLiveAgentObservations>)
  return render(
    <MemoryRouter>
      <LiveDecisionFeed items={items} isLoading={isLoading} selectedKey={selectedKey} />
    </MemoryRouter>,
  )
}

describe('LiveDecisionFeed', () => {
  it('hides entirely while overview is loading or no active agent', () => {
    const loading = setup({ isLoading: true, data: page() })
    expect(loading.container.textContent).toBe('')

    const disabled = setup({
      items: [agentItem({ profile: profile({ status: 'disabled' }) })],
      data: page(),
    })
    expect(disabled.container.textContent).toBe('')
  })

  it('shows live badge, agent link, stats and row fields during open session', () => {
    setup({
      data: page({
        items: [
          item({
            l0Verdict: 'triggered',
            triggerReason: 'buy_zone',
            decision: {
              servedModel: 'openjev-0.1',
              choice: '等待回踩',
              confidence: 0.41,
              noul: false,
              score: 3,
              window: null,
            },
            action: 'suppress',
            suppressionReason: 'below_threshold',
          }),
        ],
      }),
    })

    expect(screen.getByText('实时')).toBeInTheDocument()
    expect(screen.getByText('实时决策流')).toBeInTheDocument()
    expect(screen.getByText('短线 agent')).toHaveAttribute('href', '/trading-agent/short-line')
    expect(screen.getByText('tick 7 · 显著 1')).toBeInTheDocument()

    expect(screen.getByText(dayjs(TICK_TIME).format('HH:mm:ss'))).toBeInTheDocument()
    expect(screen.getByText('浦发银行')).toBeInTheDocument()
    expect(screen.getByText('600000')).toBeInTheDocument()
    expect(screen.getByText('10.05')).toBeInTheDocument()
    expect(screen.getByText('+0.70%')).toBeInTheDocument()
    expect(screen.getByText('抑制')).toBeInTheDocument()
    expect(screen.getByText('进入买点区间，置信不足未执行')).toBeInTheDocument()
    expect(screen.getByText('依据')).toBeInTheDocument()
    expect(screen.getByText('置信 41%（低）')).toBeInTheDocument()
    expect(screen.getByText('盘面 3.0/5 · 中性')).toBeInTheDocument()
    expect(screen.getByText('分时：不支持离场')).toBeInTheDocument()
    expect(screen.getByText('影子')).toBeInTheDocument()
    expect(screen.getByText('低于阈值')).toBeInTheDocument()
  })

  it('shows review badge with trade date when market closed', () => {
    setup({ session: 'closed', data: page() })
    expect(screen.getByText('已收盘')).toBeInTheDocument()
    expect(screen.getByText('· 回顾 2026-09-28')).toBeInTheDocument()
    expect(screen.queryByText('实时')).not.toBeInTheDocument()
  })

  it('dims heartbeat rows but not significant rows', () => {
    const { container } = setup({
      data: page({
        items: [
          item({ id: 1, l0Detail: '未触达止盈/止损价' }),
          item({ id: 2, l0Verdict: 'triggered', action: 'suppress', suppressionReason: 'below_threshold' }),
        ],
      }),
    })
    const rows = container.querySelectorAll('.opacity-40')
    expect(rows).toHaveLength(1)
    expect(rows[0].textContent).toContain('巡检正常 · 未触达止盈/止损价')
    expect(rows[0].textContent).not.toContain('openjev-0.1')
    expect(rows[0].textContent).not.toContain('依据')
  })

  it('marks tail-check rows without stock link', () => {
    const { container } = setup({
      data: page({
        items: [
          item({
            planId: null,
            planType: null,
            stockName: null,
            decision: { servedModel: null, choice: null, confidence: null, noul: null, score: null, window: 'tail_check' },
            l0Verdict: 'triggered',
            triggerReason: 'stop_loss',
            action: 'suppress',
            suppressionReason: 'shadow_mode',
          }),
        ],
      }),
    })
    expect(screen.getByText('尾盘强检')).toBeInTheDocument()
    expect(screen.getByText('600000')).toBeInTheDocument()
    expect(screen.queryByText('浦发银行')).not.toBeInTheDocument()
    expect(container.querySelector('a[href^="/stock/"]')).toBeNull()
  })

  it('renders empty hint when feed has no rows', () => {
    setup({ data: page({ items: [], total: 0 }) })
    expect(screen.getByText('暂无观测留痕')).toBeInTheDocument()
  })

  it('falls back to first active agent when selection is absent or unknown', () => {
    setup({ selectedKey: null, data: page() })
    expect(mockLive).toHaveBeenLastCalledWith('short-line')

    setup({ selectedKey: 'ghost', data: page() })
    expect(mockLive).toHaveBeenLastCalledWith('short-line')
  })

  it('switches to the stage-selected agent', () => {
    setup({
      items: [
        agentItem(),
        agentItem({
          profile: profile({ agentKey: 'long-line', name: '长线 agent' }),
          runtimeState: 'idle',
        }),
      ],
      selectedKey: 'long-line',
      data: page(),
    })
    expect(mockLive).toHaveBeenLastCalledWith('long-line')
  })

  it('ignores selecting an off agent and keeps the fallback feed', () => {
    setup({
      items: [
        agentItem(),
        agentItem({
          profile: profile({ agentKey: 'm60', name: 'M60 agent', status: 'planned' }),
          runtimeState: 'off',
        }),
      ],
      selectedKey: 'm60',
      data: page(),
    })
    expect(mockLive).toHaveBeenLastCalledWith('short-line')
  })
})
