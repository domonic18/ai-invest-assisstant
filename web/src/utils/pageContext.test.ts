import { describe, expect, it } from 'vitest'

import { buildPageContext } from './pageContext'

describe('buildPageContext', () => {
  it('解析个股详情页股票代码', () => {
    expect(buildPageContext('/stock/000001')).toEqual({
      route: '/stock/000001',
      page: '个股详情',
      stock_code: '000001',
    })
  })

  it('解析财务分析页', () => {
    const context = buildPageContext('/financial/600519')
    expect(context.page).toBe('财务分析')
    expect(context.stock_code).toBe('600519')
  })

  it('解析产业链页行业名（含中文编码）', () => {
    const context = buildPageContext(`/chain/${encodeURIComponent('半导体')}`)
    expect(context.page).toBe('产业链分析')
    expect(context.industry).toBe('半导体')
  })

  it('识别无参数的普通页面', () => {
    expect(buildPageContext('/capital-flow').page).toBe('资金流向')
    expect(buildPageContext('/').page).toBeUndefined()
  })
})
