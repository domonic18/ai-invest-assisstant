/** AccountDimension：窗口内计数 + 按日时序条 + 全账号汇总条渲染。 */

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { ApiSocialAccountCard } from '@ai-invest/shared'

import { AccountDimension } from './AccountDimension'

function account(overrides: Partial<ApiSocialAccountCard>): ApiSocialAccountCard {
  return {
    id: 1,
    alias: '财经大V',
    category: 'finance_kol',
    lastPostAt: null,
    latestStance: 'bearish',
    latestConfidence: 0.9,
    latestSummary: '短线承压',
    latestCoverUrl: null,
    bullishCount: 2,
    bearishCount: 5,
    neutralCount: 1,
    daily: [
      { date: '2026-09-15', bullish: 1, bearish: 2, neutral: 0 },
      { date: '2026-09-16', bullish: 1, bearish: 3, neutral: 1 },
    ],
    ...overrides,
  }
}

describe('AccountDimension', () => {
  it('renders window-scoped counts, aggregate strip and per-day bars', () => {
    render(
      <AccountDimension
        accounts={[
          account({}),
          account({ id: 2, alias: '宏观观察', daily: [], bullishCount: 0, bearishCount: 1, neutralCount: 0 }),
        ]}
        isLoading={false}
        selectedId={null}
        onSelect={() => undefined}
      />,
    )
    expect(screen.getByText('全账号情绪时序')).toBeTruthy()
    // 汇总条与首张卡片同时渲染「多 2」「空 5」（第二张账号无 daily/计数）
    expect(screen.getAllByText('多 2')).toHaveLength(2)
    expect(screen.getAllByText('空 5')).toHaveLength(2)
    // 两列日期标签（汇总条 showDayLabel，MM/DD）
    expect(screen.getByText('09/15')).toBeTruthy()
    expect(screen.getByText('09/16')).toBeTruthy()
  })

  it('hides aggregate strip when there are no accounts', () => {
    render(
      <AccountDimension
        accounts={[]}
        isLoading={false}
        selectedId={null}
        onSelect={() => undefined}
      />,
    )
    expect(screen.getByText('暂无追踪账号数据')).toBeTruthy()
    expect(screen.queryByText('全账号情绪时序')).toBeNull()
  })
})
