/** 交易纯规则测试：全部断言由显式偏移 fixture 推导，与 runner 时区无关。 */

import { describe, expect, it } from 'vitest'
import dayjs from 'dayjs'

import {
  isMarketOpen,
  limitPrices,
  maxBuyVolume,
  maxSellVolume,
  marketSession,
  priceLimitPct,
  SESSION_LABEL,
} from './tradingRules'

// 2026-09-21 是周一，2026-09-20 是周日
const at = (h: number, m: number) => dayjs(`2026-09-21T${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:00+08:00`)

describe('marketSession', () => {
  it('盘中两段为 open', () => {
    expect(marketSession(at(9, 30))).toBe('open')
    expect(marketSession(at(11, 29))).toBe('open')
    expect(marketSession(at(13, 0))).toBe('open')
    expect(marketSession(at(14, 59))).toBe('open')
  })

  it('午休与盘前收盘边界', () => {
    expect(marketSession(at(11, 30))).toBe('break')
    expect(marketSession(at(12, 30))).toBe('break')
    expect(marketSession(at(9, 29))).toBe('pre')
    expect(marketSession(at(8, 0))).toBe('pre')
    expect(marketSession(at(15, 0))).toBe('closed')
    expect(marketSession(at(20, 0))).toBe('closed')
  })

  it('周末为 closed', () => {
    const sunday = dayjs('2026-09-20T10:00:00+08:00')
    expect(marketSession(sunday)).toBe('closed')
    expect(isMarketOpen(sunday)).toBe(false)
  })

  it('UTC 表示与 +08:00 表示同瞬时产出一致（CI 免费 UTC 矩阵）', () => {
    const sameInstant = dayjs('2026-09-21T01:30:00Z') // 北京 09:30
    expect(marketSession(sameInstant)).toBe('open')
    expect(marketSession(sameInstant)).toBe(marketSession(at(9, 30)))
  })

  it('isMarketOpen 只在 open 为真', () => {
    expect(isMarketOpen(at(10, 0))).toBe(true)
    expect(isMarketOpen(at(12, 0))).toBe(false)
  })

  it('每个时段都有标签与提示', () => {
    for (const session of ['open', 'break', 'pre', 'closed'] as const) {
      expect(SESSION_LABEL[session].label).toBeTruthy()
      expect(SESSION_LABEL[session].hint).toBeTruthy()
    }
  })
})

describe('priceLimitPct', () => {
  it('ST ±5', () => {
    expect(priceLimitPct('ST 易联众', '000037')).toBe(5)
    expect(priceLimitPct('*ST 海航', '600221')).toBe(5)
  })

  it('创业板/科创板 ±20', () => {
    expect(priceLimitPct('宁德时代', '300750')).toBe(20)
    expect(priceLimitPct('中芯国际', '688981')).toBe(20)
  })

  it('主板 ±10', () => {
    expect(priceLimitPct('深发展A', '000001')).toBe(10)
    expect(priceLimitPct('浦发银行', '600000')).toBe(10)
  })
})

describe('limitPrices', () => {
  it('主板 ±10% 四舍五入到分', () => {
    expect(limitPrices(10.05, 10)).toEqual({ limitUp: 11.06, limitDown: 9.05 })
    expect(limitPrices(8.95, 10)).toEqual({ limitUp: 9.85, limitDown: 8.06 })
  })

  it('ST ±5%', () => {
    expect(limitPrices(10.0, 5)).toEqual({ limitUp: 10.5, limitDown: 9.5 })
  })
})

describe('maxBuyVolume', () => {
  it('向下取整到手', () => {
    expect(maxBuyVolume(100000, 8.95)).toBe(11100)
    expect(maxBuyVolume(894, 8.95)).toBe(0)
    expect(maxBuyVolume(895, 8.95)).toBe(100)
  })

  it('非法输入为 0', () => {
    expect(maxBuyVolume(1000, 0)).toBe(0)
    expect(maxBuyVolume(-1, 10)).toBe(0)
  })
})

describe('maxSellVolume', () => {
  it('向下取整到手，不足一手为 0', () => {
    expect(maxSellVolume(1234)).toBe(1200)
    expect(maxSellVolume(99)).toBe(0)
    expect(maxSellVolume(0)).toBe(0)
  })
})
