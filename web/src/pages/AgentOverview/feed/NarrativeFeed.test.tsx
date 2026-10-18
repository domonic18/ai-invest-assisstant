import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import type { ApiTradingAgentObservationItem } from '@ai-invest/shared'

import { NarrativeFeed } from './NarrativeFeed'

import { makeOverviewItem } from '../testFixtures'

function makeObservation(
  id: number,
  overrides: Partial<ApiTradingAgentObservationItem> = {},
): ApiTradingAgentObservationItem {
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
    ...overrides,
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
      items: Array.from({ length: 12 }, (_, i) =>
        makeObservation(i + 1, { stockCode: String(600000 + i) }),
      ),
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

  it('连续同股同事件条目合并为最新一条 + N 徽标', () => {
    const feed = {
      tradeDate: '2026-09-30',
      total: 6,
      page: 1,
      pageSize: 12,
      items: [
        ...Array.from({ length: 5 }, (_, i) => makeObservation(i + 1)),
        makeObservation(6, { stockCode: '000001.SZ', stockName: '平安银行' }),
      ],
      summary: {
        totalTicks: 6,
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
    expect(container.querySelectorAll('.ahc-feed-card')).toHaveLength(2)
    expect(screen.getByText('+4')).toBeInTheDocument()
  })

  it('同股连发超过展示卡片数时 +N 不被截断（先合并后截断）', () => {
    // 15 条连续心跳（> 8 卡上限）：整段合并为 1 张卡，+14 反映真实观测数
    const feed = {
      tradeDate: '2026-09-30',
      total: 15,
      page: 1,
      pageSize: 60,
      items: Array.from({ length: 15 }, (_, i) => makeObservation(i + 1)),
      summary: {
        totalTicks: 15,
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
    expect(container.querySelectorAll('.ahc-feed-card')).toHaveLength(1)
    expect(screen.getByText('+14')).toBeInTheDocument()
  })

  it('合并卡保留最新一条的时间（输入最新在前）', () => {
    const feed = {
      tradeDate: '2026-09-30',
      total: 3,
      page: 1,
      pageSize: 12,
      items: Array.from({ length: 3 }, (_, i) => makeObservation(i + 1)),
      summary: {
        totalTicks: 3,
        significantTicks: 0,
        l0VerdictCounts: {},
        actionCounts: {},
        suppressionCounts: {},
      },
    }
    render(
      <MemoryRouter>
        <NarrativeFeed {...PROPS} feed={feed} />
      </MemoryRouter>,
    )
    // id=1 为最新（tickTime 13:58），合并卡应显示它而非更早的 13:57/13:56
    expect(screen.getByText('13:58:00')).toBeInTheDocument()
    expect(screen.queryByText('13:56:00')).not.toBeInTheDocument()
  })

  it('事件类型不同的相邻条目不合并', () => {
    const feed = {
      tradeDate: '2026-09-30',
      total: 2,
      page: 1,
      pageSize: 12,
      items: [
        makeObservation(1),
        makeObservation(2, { action: 'wait', l0Detail: '量未放大' }),
      ],
      summary: {
        totalTicks: 2,
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
    expect(container.querySelectorAll('.ahc-feed-card')).toHaveLength(2)
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
