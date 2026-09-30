import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import type { ApiTradingAgentObservationItem } from '@ai-invest/shared'

import { NarrativeFeed } from './NarrativeFeed'

import { makeOverviewItem } from '../testFixtures'

function makeObservation(id: number): ApiTradingAgentObservationItem {
  return {
    id,
    tickTime: `2026-09-30T13:${String(59 - id).padStart(2, '0')}:00+08:00`,
    tradeDate: '2026-09-30',
    agentKey: 'hunter',
    planId: null,
    stockCode: '600000.SH',
    stockName: '浦发银行',
    planType: null,
    price: 10.98,
    changePct: 1.2,
    l0Verdict: 'no_action',
    triggerReason: null,
    l0Detail: null,
    decision: null,
    action: null,
    suppressionReason: null,
    isShadow: true,
    clOrdId: null,
    orderVolume: null,
  }
}

const PROPS = {
  agent: makeOverviewItem(),
  feedLoading: false,
}

describe('NarrativeFeed', () => {
  it('决策流最多渲染 8 张卡（整页一屏约束）', () => {
    const feed = {
      tradeDate: '2026-09-30',
      total: 12,
      page: 1,
      pageSize: 12,
      items: Array.from({ length: 12 }, (_, i) => makeObservation(i + 1)),
      summary: {
        totalTicks: 12,
        significantTicks: 0,
        l0VerdictCounts: {},
        actionCounts: {},
        suppressionCounts: {},
      },
    }
    const { container } = render(
      <MemoryRouter>
        <NarrativeFeed {...PROPS} feed={feed} />
      </MemoryRouter>,
    )
    expect(container.querySelectorAll('.ahc-feed-card')).toHaveLength(8)
    expect(screen.getByText('实时决策流')).toBeInTheDocument()
  })

  it('无观测数据渲染空态', () => {
    render(
      <MemoryRouter>
        <NarrativeFeed
          {...PROPS}
          feed={{
            tradeDate: '2026-09-30',
            total: 0,
            page: 1,
            pageSize: 12,
            items: [],
            summary: {
              totalTicks: 0,
              significantTicks: 0,
              l0VerdictCounts: {},
              actionCounts: {},
              suppressionCounts: {},
            },
          }}
        />
      </MemoryRouter>,
    )
    expect(screen.getByText('暂无观测留痕')).toBeInTheDocument()
  })
})
