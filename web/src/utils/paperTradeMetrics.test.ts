import { describe, expect, it } from 'vitest'

import { cumPnl, dailyPnl } from './paperTradeMetrics'

describe('cumPnl', () => {
  it('盈亏与百分比按 cumInout 为分母（盈利）', () => {
    expect(cumPnl({ nav: 101000, cumInout: 100000 })).toEqual({ pnl: 1000, pnlPct: 1 })
  })

  it('亏损为负值', () => {
    expect(cumPnl({ nav: 99000, cumInout: 100000 })).toEqual({ pnl: -1000, pnlPct: -1 })
  })

  it('cash 或字段缺失返回 null', () => {
    expect(cumPnl(null)).toEqual({ pnl: null, pnlPct: null })
    expect(cumPnl({ nav: null, cumInout: 100000 })).toEqual({ pnl: null, pnlPct: null })
  })

  it('cumInout 为 0 时百分比 null、金额仍计算', () => {
    expect(cumPnl({ nav: 500, cumInout: 0 })).toEqual({ pnl: 500, pnlPct: null })
  })
})

describe('dailyPnl', () => {
  it('实时 nav − 前一快照 nav − 期间出入金增量', () => {
    const items = [
      { tradeDate: '2026-09-29', nav: 100000, cumInout: 100000 },
      { tradeDate: '2026-09-30', nav: 100500, cumInout: 100000 },
    ]
    expect(dailyPnl(items, { nav: 100300, cumInout: 100000 })).toEqual({
      dayPnl: -200,
      dayPnlPct: (-200 / 100500) * 100,
    })
  })

  it('无昨日基准快照返回 null（仅有「未来」快照或无快照）', () => {
    const future = '2999-12-31'
    expect(dailyPnl([{ tradeDate: future, nav: 100000, cumInout: 100000 }], { nav: 100000, cumInout: 100000 }).dayPnl).toBeNull()
    expect(dailyPnl(undefined, { nav: 100000, cumInout: 100000 }).dayPnl).toBeNull()
  })
})
